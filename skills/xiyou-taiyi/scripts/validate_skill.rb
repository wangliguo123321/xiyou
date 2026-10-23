#!/usr/bin/env ruby
# 独立 Ruby 适配；来源与 Apache-2.0 说明见 ../references/lineage.md、../NOTICE.txt。
begin
  require 'json'
  require 'psych'
  require 'date'
rescue LoadError
  puts '{"schema_version":1,"status":"error","results":[],"errors":[{"code":"environment","message":"缺少 Ruby 标准库 JSON、Psych 或 date。"}]}'
  exit 2
end

MAX_FILE_BYTES = 262_144
FIELDS = %w[name description license allowed-tools metadata compatibility].freeze
SAFE_TAGS = %w[null bool int float str seq map binary timestamp].map do |name|
  "tag:yaml.org,2002:#{name}"
end.freeze

def issue(code, message, field = nil)
  item = { 'code' => code, 'message' => message }
  item['field'] = field if field
  item
end

def emit(status, results, errors = [], extra = {})
  puts JSON.generate({ 'schema_version' => 1, 'status' => status,
                       'results' => results, 'errors' => errors }.merge(extra))
end

def validate_directory(directory)
  result = { 'directory' => directory, 'status' => 'invalid', 'errors' => [] }
  errors = result['errors']
  unless File.directory?(directory)
    result['status'] = 'error'
    errors << issue('directory_unavailable', '输入必须是可访问的技能目录。')
    return result
  end
  path = File.join(directory, 'SKILL.md')
  begin
    File.lstat(path)
  rescue Errno::ENOENT
    errors << issue('skill_missing', '技能目录缺少 SKILL.md。')
    return result
  end
  unless File.file?(path)
    result['status'] = 'error'
    errors << issue('not_regular_file', 'SKILL.md 必须是普通文件。')
    return result
  end
  content = File.open(path, 'rb') { |file| file.read(MAX_FILE_BYTES + 1) }.to_s
  if content.bytesize > MAX_FILE_BYTES
    result['status'] = 'error'
    errors << issue('file_too_large', "SKILL.md 超过 #{MAX_FILE_BYTES} 字节，未完成检查。")
    return result
  end
  content.force_encoding(Encoding::UTF_8)
  unless content.valid_encoding?
    errors << issue('invalid_utf8', 'SKILL.md 必须是有效 UTF-8 文本。')
    return result
  end
  match = content.sub(/\A\uFEFF/, '').match(/\A---\r?\n(.*?)^---\r?$(?:\n|\z)/m)
  unless match
    errors << issue('frontmatter_missing', '文件开头须有以独立 --- 行包围的 YAML 元数据。')
    return result
  end
  yaml = match[1]
  stream = Psych.parse_stream(yaml)
  root = stream.children.first&.root
  unless stream.children.length == 1 && root.is_a?(Psych::Nodes::Mapping)
    errors << issue('frontmatter_not_mapping', '元数据须是单一 YAML 字典。')
    return result
  end
  nodes = [stream]
  unsafe_tag = false
  alias_found = false
  until nodes.empty?
    node = nodes.pop
    unsafe_tag ||= node.respond_to?(:tag) && node.tag && !SAFE_TAGS.include?(node.tag)
    alias_found ||= node.is_a?(Psych::Nodes::Alias)
    nodes.concat(node.children || [])
  end
  errors << issue('unsafe_tag', '不接受 Ruby 或自定义 YAML 标签。') if unsafe_tag
  errors << issue('yaml_alias', '不接受 YAML 别名。') if alias_found
  seen = {}
  root.children.each_slice(2) do |key, _value|
    unless key.is_a?(Psych::Nodes::Scalar)
      errors << issue('invalid_key', '顶层字段名必须是字符串。')
      next
    end
    unless FIELDS.include?(key.value)
      errors << issue('unknown_field', '顶层字段不在允许列表内。', key.value[0, 80])
    end
    if seen[key.value]
      errors << issue('duplicate_field', '顶层字段重复。', key.value[0, 80])
    end
    seen[key.value] = true
  end
  return result unless errors.empty?

  data = Psych.safe_load(yaml, permitted_classes: [Date, Time], permitted_symbols: [], aliases: false)
  unless data.is_a?(Hash)
    errors << issue('frontmatter_not_mapping', '安全解析后的元数据须为 YAML 字典。')
    return result
  end
  %w[name description].each do |field|
    unless data[field].is_a?(String) && !data[field].strip.empty?
      errors << issue('required_string', '必需字段须为非空字符串。', field)
    end
  end
  name = data['name']
  if name.is_a?(String) && (name.length > 64 || !/\A[a-z0-9]+(?:-[a-z0-9]+)*\z/.match?(name))
    errors << issue('invalid_name', '名称须为小写字母数字及单连字符，不首尾连字符，最多 64 字符。', 'name')
  end
  description = data['description']
  if description.is_a?(String) && (description.length > 1024 || /[<>]/.match?(description))
    errors << issue('invalid_description', '描述最多 1024 字符且不含尖括号。', 'description')
  end
  if data.key?('compatibility') && (!data['compatibility'].is_a?(String) || data['compatibility'].length > 500)
    errors << issue('invalid_compatibility', '出现 compatibility 时须为最多 500 字符的字符串。', 'compatibility')
  end
  result['status'] = 'passed' if errors.empty?
  result
rescue Psych::Exception, ArgumentError, SystemStackError
  errors << issue('invalid_yaml', 'YAML 无法安全解析或嵌套超出解析能力。')
  result
rescue SystemCallError, IOError, SecurityError
  result['status'] = 'error'
  errors << issue('read_error', '无法读取技能目录中的 SKILL.md。')
  result
end

if ARGV == ['--help']
  emit('help', [], [], 'usage' => 'ruby validate_skill.rb [--] 技能目录 [技能目录 ...]',
       'max_file_bytes' => MAX_FILE_BYTES, 'exit_codes' => { '0' => '全部有效', '1' => '结构无效', '2' => '使用或读取障碍' })
  exit 0
end
directories = ARGV.dup
literal_paths = directories.first == '--'
directories.shift if literal_paths
if directories.empty? || directories.any? { |path| !path.valid_encoding? || (!literal_paths && path.start_with?('-')) }
  emit('error', [], [issue('usage', '须提供一个或多个显式技能目录；用 --help 查看用法。')])
  exit 2
end
results = directories.map { |directory| validate_directory(directory) }
status = if results.any? { |result| result['status'] == 'error' }
           'error'
         elsif results.any? { |result| result['status'] == 'invalid' }
           'invalid'
         else
           'passed'
         end
emit(status, results)
exit({ 'passed' => 0, 'invalid' => 1, 'error' => 2 }.fetch(status))
