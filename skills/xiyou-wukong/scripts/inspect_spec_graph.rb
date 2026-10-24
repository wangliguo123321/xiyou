#!/usr/bin/env ruby
# 独立 Ruby/Psych 只读适配，来源、版权及改动见 ../NOTICE.txt。
begin
  require 'json'
  require 'psych'
  require 'date'
rescue LoadError
  puts '{"schema_version":1,"status":"error","scan_complete":false,"errors":[{"code":"environment","message":"需要 Ruby 标准库 JSON、Psych 和 date。"}]}'
  exit 2
end

KINDS = %w[parent depends-on references implements].freeze
MODES = %w[neighbors ancestors subtree validate].freeze
IGNORED = %w[node_modules .git dist build .claude .superpowers .gsd .mockups .playwright-mcp].freeze
MAX_FILE = 524_288
MAX_TOTAL = 16_777_216
MAX_FILES = 1024
SAFE_TAGS = %w[null bool int float str seq map binary timestamp].map { |s| "tag:yaml.org,2002:#{s}" }.freeze

def order(value)
  [value.unicode_normalize(:nfc), value]
end

def problem(errors, code, message, path = nil, field = nil)
  item = { code: code, message: message }
  item[:path] = path if path
  item[:field] = field if field
  errors << item
end

def parse_node(text, path, errors)
  lines = text.sub(/\A\uFEFF/, '').lines
  return nil unless lines.first && lines.first.strip == '---'
  last = (1...lines.length).find { |i| lines[i].strip == '---' }
  unless last
    problem(errors, 'unclosed_frontmatter', '开头的 frontmatter 未闭合。', path)
    return nil
  end
  yaml = lines[1...last].join
  stream = Psych.parse_stream(yaml)
  return nil if stream.children.empty?
  root = stream.children.first&.root
  unless stream.children.length == 1
    problem(errors, 'invalid_yaml', 'frontmatter 必须是单一 YAML 文档。', path)
    return nil
  end
  pending = [stream]
  until pending.empty?
    part = pending.pop
    if part.is_a?(Psych::Nodes::Alias) || (part.respond_to?(:tag) && part.tag && !SAFE_TAGS.include?(part.tag))
      problem(errors, 'unsupported_yaml', '不接受 YAML 别名、对象或自定义标签。', path)
      return nil
    end
    pending.concat(part.children || [])
  end
  if root.is_a?(Psych::Nodes::Mapping)
    seen = {}
    root.children.each_slice(2) do |key, _value|
      unless key.is_a?(Psych::Nodes::Scalar)
        problem(errors, 'unsupported_yaml', '顶层复合字段名不在只读方言内。', path)
        return nil
      end
      if seen[key.value]
        problem(errors, 'duplicate_key', '顶层 YAML 字段重复。', path, key.value)
        return nil
      end
      seen[key.value] = true
    end
  end
  data = Psych.safe_load(yaml, permitted_classes: [Date, Time], permitted_symbols: [], aliases: false)
  return nil unless data.is_a?(Hash) && data.key?('id') && data.key?('type')
  before = errors.length
  %w[id type].each do |field|
    unless data[field].is_a?(String) && data[field].encoding == Encoding::UTF_8 && data[field].valid_encoding?
      problem(errors, 'unsupported_field', '身份字段须为字符串；不会重解释 YAML 标量。', path, field)
    end
  end
  return nil unless errors.length == before
  return nil if data['id'].strip.empty? || data['type'].strip.empty?
  links = {}
  KINDS.each do |kind|
    value = data[kind]
    next unless data.key?(kind)
    targets = kind == 'parent' ? [value] : (value.is_a?(Array) ? value : [value])
    unless targets.all? { |target| target.is_a?(String) && target.encoding == Encoding::UTF_8 && target.valid_encoding? }
      problem(errors, 'unsupported_field', '关系须为字符串，列表关系也可为字符串数组。', path, kind)
      next
    end
    links[kind] = if value.is_a?(String)
                    value.empty? ? [] : [value]
                  else
                    targets
                  end
  end
  return nil unless errors.length == before
  node = { id: data['id'], type: data['type'], path: path }
  node[:title] = data['title'] if data['title'].is_a?(String) && data['title'].encoding == Encoding::UTF_8 && data['title'].valid_encoding?
  [node, links]
rescue Psych::Exception, ArgumentError, SystemStackError
  problem(errors, 'invalid_yaml', 'YAML 无法安全解析或超出解析能力。', path)
  nil
end

def scan(root, errors, stats)
  entries = []
  stack = ['']
  until stack.empty?
    relative = stack.pop
    path = relative.empty? ? root : File.join(root, relative)
    begin
      info = File.lstat(path)
      if info.symlink? || (!info.directory? && !info.file?)
        stats[:skipped_special] += 1
        next
      end
      if info.directory?
        names = Dir.children(path)
        safe = names.select do |name|
          if name.valid_encoding?
            true
          else
            problem(errors, 'invalid_path_encoding', '目录含无法表示的文件名。', relative.scrub)
            false
          end
        end
        safe.sort_by { |name| order(name) }.reverse_each do |name|
          child = relative.empty? ? name : File.join(relative, name)
          next if IGNORED.include?(name) && File.lstat(File.join(root, child)).directory?
          stack << child
        end
        next
      end
      next unless relative.end_with?('.md')
      stats[:markdown_files] += 1
      if stats[:markdown_files] > MAX_FILES
        problem(errors, 'file_count_limit', "超过 #{MAX_FILES} 份 Markdown，扫描未完成。", relative)
        break
      end
      if info.size > MAX_FILE
        problem(errors, 'file_size_limit', "Markdown 超过 #{MAX_FILE} 字节。", relative)
        next
      end
      if stats[:bytes_read] + info.size > MAX_TOTAL
        problem(errors, 'total_size_limit', "超过 #{MAX_TOTAL} 字节扫描预算。", relative)
        break
      end
      content = File.open(path, File::RDONLY | File::NOFOLLOW | File::NONBLOCK) do |file|
        opened = file.stat
        unless opened.file? && opened.dev == info.dev && opened.ino == info.ino
          raise IOError, '文件身份发生变化'
        end
        bytes = file.read([MAX_FILE + 1, MAX_TOTAL - stats[:bytes_read] + 1].min).to_s
        after = file.stat
        unless opened.size == after.size && opened.mtime == after.mtime && bytes.bytesize == opened.size
          raise IOError, '读取期间文件发生变化'
        end
        bytes
      end
      stats[:bytes_read] += content.bytesize
      if content.bytesize > MAX_FILE || stats[:bytes_read] > MAX_TOTAL
        problem(errors, 'read_size_limit', '读取内容超出字节预算。', relative)
        next
      end
      stats[:read_files] += 1
      content.force_encoding(Encoding::UTF_8)
      unless content.valid_encoding?
        problem(errors, 'invalid_utf8', 'Markdown 不是有效 UTF-8。', relative)
        next
      end
      before = errors.length
      item = parse_node(content, relative, errors)
      if item
        entries << item
      else
        stats[:skipped_non_spec] += 1 if errors.length == before
      end
    rescue SystemCallError, IOError, SecurityError
      problem(errors, 'read_error', '无法完整读取目录或普通 Markdown 文件。', relative.scrub)
    end
  end
  entries
end

def build_graph(entries)
  nodes, links, paths = {}, {}, Hash.new { |h, k| h[k] = [] }
  entries.each do |node, relationships|
    id = node[:id]
    paths[id] << node[:path]
    next if nodes.key?(id)
    nodes[id], links[id] = node, relationships
  end
  edges = links.flat_map do |id, relationships|
    relationships.flat_map { |kind, targets| targets.map { |to| { from: id, to: to, kind: kind } } }
  end.uniq.sort_by { |edge| [order(edge[:from]), edge[:kind], order(edge[:to])] }
  duplicates = paths.select { |_id, all| all.length > 1 }.map { |id, all| { id: id, paths: all } }
  dangling = edges.reject { |edge| nodes.key?(edge[:to]) }.map do |edge|
    { from: edge[:from], from_path: nodes[edge[:from]][:path], kind: edge[:kind], target: edge[:to] }
  end
  parents = edges.select { |edge| edge[:kind] == 'parent' }.to_h { |edge| [edge[:from], edge[:to]] }
  seen, cycles = {}, []
  nodes.keys.sort_by { |id| order(id) }.each do |start|
    trail, positions, current = [], {}, start
    while nodes.key?(current) && !seen[current]
      if positions.key?(current)
        ring = trail[positions[current]..-1]
        first = ring.each_index.min_by { |i| order(ring[i]) }
        ring = ring.rotate(first)
        cycles << { ids: ring, paths: ring.map { |id| nodes[id][:path] } }
        break
      end
      positions[current] = trail.length
      trail << current
      current = parents[current]
    end
    trail.each { |id| seen[id] = true }
  end
  [nodes, edges, { dangling_links: dangling, duplicate_ids: duplicates.sort_by { |d| order(d[:id]) },
                   parent_cycles: cycles.sort_by { |cycle| order(cycle[:ids].first) } }]
end

def slice(nodes, edges, options)
  kind = options[:mode] == 'neighbors' ? options[:kind] : 'parent'
  relevant = edges.select { |edge| edge[:kind] == kind }
  forward, reverse = Hash.new { |h, k| h[k] = [] }, Hash.new { |h, k| h[k] = [] }
  relevant.each do |edge|
    forward[edge[:from]] << edge[:to]
    reverse[edge[:to]] << edge[:from]
  end
  included, frontier = { options[:id] => true }, [options[:id]]
  options[:depth].times do
    following = []
    frontier.each do |id|
      targets = case options[:mode]
                when 'ancestors' then forward[id]
                when 'subtree' then reverse[id]
                else forward[id] + reverse[id]
                end
      targets.each do |target|
        next if included[target]
        included[target] = true
        following << target
      end
    end
    frontier = following
    break if frontier.empty?
  end
  selected = included.keys.sort_by { |id| order(id) }
  [selected.map { |id| nodes[id] }.compact,
   relevant.select { |edge| included[edge[:from]] && included[edge[:to]] && nodes.key?(edge[:to]) },
   selected.reject { |id| nodes.key?(id) }]
end

options = { mode: 'neighbors', kind: 'depends-on', depth: 1 }
errors = []
result = { schema_version: 1, status: 'error', scan_complete: false, errors: errors }
begin
  if ARGV == ['--help']
    puts JSON.generate(result.merge(status: 'help', usage: 'ruby inspect_spec_graph.rb --root DIR [--mode neighbors|ancestors|subtree|validate] [--id ID] [--kind parent|depends-on|references|implements] [--depth 0..8]', exit_codes: { '0' => '完整且有效', '1' => '完整但图或请求无效', '2' => '使用、解析或不完整障碍' }))
    exit 0
  end
  arguments, supplied = ARGV.dup, {}
  until arguments.empty?
    flag, value = arguments.shift, arguments.shift
    unless %w[--root --mode --id --kind --depth].include?(flag) && value && !supplied[flag] && value.valid_encoding?
      raise ArgumentError, '参数须使用唯一的 --选项 值；--help 查看用法。'
    end
    supplied[flag] = true
    options[flag[2..-1].to_sym] = value
  end
  raise ArgumentError, '必须显式指定 --root 目录。' unless options[:root] && !options[:root].empty?
  raise ArgumentError, '未知 --mode 或 --kind。' unless MODES.include?(options[:mode]) && KINDS.include?(options[:kind])
  depth = options[:depth].to_s
  raise ArgumentError, '--depth 必须是 0..8 的整数。' unless /\A[0-8]\z/.match?(depth)
  options[:depth] = depth.to_i
  if options[:mode] != 'validate' && (!options[:id] || options[:id].strip.empty?)
    raise ArgumentError, '图查询须指定非空 --id。'
  end
  root = File.expand_path(options[:root])
  raise ArgumentError, '--root 必须是普通可访问目录，不能是符号链接。' unless File.lstat(root).directory?
  stats = { markdown_files: 0, read_files: 0, bytes_read: 0, skipped_special: 0, skipped_non_spec: 0 }
  result.merge!(root: root, mode: options[:mode], query: options.reject { |key, _| key == :root }, index: stats)
  entries = scan(root, errors, stats)
  nodes, edges, diagnostics = build_graph(entries)
  stats.merge!(node_files: entries.length, nodes: nodes.length, edges: edges.length)
  result.merge!(scan_complete: errors.empty?, diagnostics: diagnostics, nodes: [], edges: [], missing_targets: [])
  requests = []
  problem(requests, 'empty_graph', '未识别到规范节点，不能证明规范图有效。') if nodes.empty?
  if options[:mode] == 'validate'
    result.merge!(nodes: nodes.values.sort_by { |node| order(node[:id]) }, edges: edges,
                  missing_targets: diagnostics[:dangling_links].map { |d| d[:target] }.uniq.sort_by { |id| order(id) })
  elsif !diagnostics[:duplicate_ids].empty?
    result.delete(:nodes)
    result.delete(:edges)
    problem(requests, 'ambiguous_graph', '图中 ID 重复；不返回可能选择任意身份的查询切片。')
  elsif !nodes.key?(options[:id])
    problem(requests, 'unknown_id', '未找到请求的规范 ID。')
  else
    selected, selected_edges, missing = slice(nodes, edges, options)
    result.merge!(nodes: selected, edges: selected_edges, missing_targets: missing)
  end
  diagnostics[:request_errors] = requests
  invalid = diagnostics.values.any? { |items| !items.empty? }
  result[:status] = errors.empty? ? (invalid ? 'invalid' : 'valid') : 'partial'
rescue ArgumentError => error
  problem(errors, 'usage', error.message)
rescue SystemCallError, IOError, SecurityError
  problem(errors, 'input_error', '根目录不可访问或扫描无法完成。')
rescue NameError, EncodingError, SystemStackError
  problem(errors, 'environment_or_input', '运行时能力不足或输入超出安全处理能力。')
end
puts JSON.generate(result)
exit({ 'valid' => 0, 'invalid' => 1 }.fetch(result[:status], 2))
