#!/usr/bin/env ruby
# 本地新写的只读 Ruby/Psych AST 适配，Apache-2.0。
# 方法来源：Copyright GitHub, Inc. / github/awesome-copilot，MIT。
# 固定源 98b45a78d3ed316e78f005b60594d5c4a50588e3：
# skills/github-actions-hardening/SKILL.md；原源没有此库存 helper。
# 2026-10-28 修改：显式输入、位置库存、有限字面分类及未知/错误边界。
# 完整归属/许可：../NOTICE.txt、../licenses/github-actions-hardening.txt。

require 'digest'
require 'json'
require 'optparse'
require 'psych'

MAX_INPUT = 2 * 1024 * 1024
MAX_NODES = 50_000
MAX_DEPTH = 64
MAX_REFS = 2000
MAX_SCALAR = 4096

class WorkflowError < StandardError
  attr_reader :code
  def initialize(code, message)
    @code = code
    super(message)
  end
end

class UnresolvedYaml < StandardError; end

def read_source(name)
  path = File.expand_path(name)
  unless File.lstat(path).file?
    raise WorkflowError.new('invalid_input', '输入必须是普通文件，不能是符号链接或特殊文件。')
  end
  flags = File::RDONLY
  flags |= File::NOFOLLOW if File.const_defined?(:NOFOLLOW)
  flags |= File::NONBLOCK if File.const_defined?(:NONBLOCK)
  data = File.open(path, flags) do |file|
    unless file.stat.file?
      raise WorkflowError.new('invalid_input', '输入必须是普通文件。')
    end
    file.binmode
    file.read(MAX_INPUT + 1) || ''.b
  end
  if data.bytesize > MAX_INPUT
    raise WorkflowError.new('input_limit', '输入超过 2 MiB。')
  end
  data
rescue SystemCallError, IOError, ArgumentError, EncodingError
  raise WorkflowError.new('input_read_failed', '无法读取指定普通文件。')
end

def ast_budget(stream)
  stack = [[stream, 0]]
  count = 0
  until stack.empty?
    node, depth = stack.pop
    count += 1
    if count > MAX_NODES || depth > MAX_DEPTH
      raise WorkflowError.new('ast_limit', 'YAML 节点数量或深度超过本接口上限。')
    end
    (node.children || []).reverse_each { |child| stack << [child, depth + 1] }
  end
end

def known_tag(node, tag)
  if node.is_a?(Psych::Nodes::Alias) || (node.respond_to?(:tag) && node.tag && node.tag != tag)
    raise UnresolvedYaml, '相关 YAML 别名或标签未解释。'
  end
end

def scalar(node)
  known_tag(node, 'tag:yaml.org,2002:str')
  unless node.is_a?(Psych::Nodes::Scalar)
    raise WorkflowError.new('invalid_structure', '采用的标量字段类型不符。')
  end
  value = node.value
  unless value.is_a?(String) && value.valid_encoding? && !value.empty? &&
         value.bytesize <= MAX_SCALAR && !value.match?(/\p{Cc}/)
    raise WorkflowError.new('invalid_metadata', '采用的标量须为有界、非空 UTF-8 文本且不含控制字符。')
  end
  value
end

def mapping(node)
  known_tag(node, 'tag:yaml.org,2002:map')
  unless node.is_a?(Psych::Nodes::Mapping)
    raise WorkflowError.new('invalid_structure', '采用的映射字段类型不符。')
  end
  fields = {}
  node.children.each_slice(2) do |key, value|
    unless key.is_a?(Psych::Nodes::Scalar)
      raise UnresolvedYaml, '相关 YAML 复杂键或别名未解释。'
    end
    name = scalar(key)
    raise UnresolvedYaml, '相关 YAML 合并键未解释。' if name == '<<'
    if fields.key?(name)
      raise WorkflowError.new('duplicate_key', '相关映射含重复键，不能确认声明引用。')
    end
    fields[name] = value
  end
  fields
end

def sequence(node)
  known_tag(node, 'tag:yaml.org,2002:seq')
  unless node.is_a?(Psych::Nodes::Sequence)
    raise WorkflowError.new('invalid_structure', 'steps 必须是列表。')
  end
  node.children
end

def reference_form(value)
  return 'dynamic' if value.include?('${{')
  return 'unknown' if value.start_with?('$/')
  return 'local' if value.start_with?('./') && !value.match?(/[[:space:]]/)
  if value.start_with?('docker://')
    return 'docker_digest64' if value.match?(/\Adocker:\/\/[^[:space:]@]+@sha256:[0-9a-fA-F]{64}\z/)
    return 'docker_named' if value.match?(/\Adocker:\/\/[^[:space:]@]+\z/)
    return 'unknown'
  end
  match = value.match(/\A[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(?:\/[A-Za-z0-9_.\/-]+)?@([^[:space:]@]+)\z/)
  return 'unknown' unless match
  match[1].match?(/\A[0-9a-fA-F]{40}\z/) ? 'remote_sha40' : 'remote_named'
end

def add_reference(refs, node, job_id, scope, step_index)
  value = scalar(node)
  if refs.length >= MAX_REFS
    raise WorkflowError.new('reference_limit', '声明引用超过 2000。')
  end
  refs << {
    scope: scope, job_id: job_id, step_index: step_index,
    line: node.start_line + 1, column: node.start_column + 1,
    uses: value, form: reference_form(value)
  }
end

def inspect_workflow(text)
  stream = Psych.parse_stream(text)
  ast_budget(stream)
  unless stream.children.length == 1 && stream.children.first.root
    raise WorkflowError.new('invalid_document', '需要恰好一个非空 YAML 文档。')
  end
  root = mapping(stream.children.first.root)
  unless root.key?('jobs')
    raise WorkflowError.new('missing_jobs', '需要显式 jobs 映射。')
  end
  refs = []
  mapping(root['jobs']).each do |job_id, node|
    job = mapping(node)
    add_reference(refs, job['uses'], job_id, 'job', nil) if job.key?('uses')
    next unless job.key?('steps')
    sequence(job['steps']).each_with_index do |step_node, index|
      step = mapping(step_node)
      add_reference(refs, step['uses'], job_id, 'step', index + 1) if step.key?('uses')
    end
  end
  refs
end

def main(argv)
  result = {
    status: 'error', source: nil, reference_count: nil, references: [],
    reason: nil, error: nil, verification: 'not_performed'
  }
  begin
    input = nil
    parser = OptionParser.new { |opts| opts.on('--input FILE') { |name| input = name } }
    parser.parse!(argv)
    if input.nil? || !argv.empty?
      raise WorkflowError.new('invalid_arguments', '需要 --input 指定本地 workflow YAML 文件。')
    end
    data = read_source(input)
    result[:source] = { sha256: Digest::SHA256.hexdigest(data), bytes: data.bytesize }
    text = data.dup.force_encoding(Encoding::UTF_8)
    unless text.valid_encoding?
      raise WorkflowError.new('invalid_encoding', '输入必须为有效 UTF-8。')
    end
    refs = inspect_workflow(text)
    unknown = refs.any? { |ref| %w[dynamic unknown].include?(ref[:form]) }
    result.merge!(status: unknown ? 'partial' : 'complete', reference_count: refs.length,
                  references: refs, reason: unknown ? 'reference_form_unresolved' : nil)
  rescue UnresolvedYaml
    result.merge!(status: 'partial', reason: 'yaml_structure_unresolved')
  rescue WorkflowError => error
    result[:error] = { code: error.code, message: error.message }
  rescue OptionParser::ParseError
    result[:error] = { code: 'invalid_arguments', message: '参数无效；需要 --input 指定本地文件。' }
  rescue Psych::Exception, ArgumentError, EncodingError, SystemStackError
    result[:error] = { code: 'invalid_yaml', message: 'YAML 无法解析或超出解析能力。' }
  end
  puts JSON.generate(result)
  { 'complete' => 0, 'partial' => 2, 'error' => 1 }[result[:status]]
end

exit main(ARGV)
