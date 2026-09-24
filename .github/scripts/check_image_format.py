#!/usr/bin/env python3
"""
检查 GitHub Issue body 是否符合镜像格式要求
"""
import os
import sys
import re


def is_valid_image_format(text):
    """
    检查文本是否符合 Docker 镜像格式
    
    支持的格式：
    1. image:tag
    2. registry/repo/image:tag
    3. registry:port/repo/image:tag
    4. image@sha256:digest
    5. registry/repo/image@sha256:digest
    6. registry/repo/image:tag@sha256:digest (虽然少见，但合法)
    
    Args:
        text: Issue body 文本
        
    Returns:
        tuple: (is_valid: bool, message: str, image_count: int)
    """
    if not text or not text.strip():
        return False, "Issue body 为空", 0
    
    lines = text.strip().split('\n')
    
    # 过滤空行
    lines = [line.strip() for line in lines if line.strip()]
    
    if len(lines) < 1:
        return False, "至少需要一行内容", 0
    
    # 跳过第一行（标题/描述）
    image_lines = lines[1:] if len(lines) > 1 else lines
    
    if not image_lines:
        return False, "没有找到镜像列表（第一行会被当作标题跳过）", 0
    
    # Docker 镜像格式正则（支持 tag 和 digest）
    # 组件说明：
    # - registry: 可选的仓库地址，支持域名和端口
    # - repository: 仓库路径，支持多级目录
    # - tag: 可选的标签
    # - digest: 可选的 digest (sha256:xxx)
    image_pattern = re.compile(
        r'^'
        # 可选的 registry (域名或 IP + 可选端口)
        r'(?:'
            r'(?P<registry>'
                r'(?:'
                    # 域名格式
                    r'(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)*'
                    r'[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?'
                r'|'
                    # IP 地址格式
                    r'(?:[0-9]{1,3}\.){3}[0-9]{1,3}'
                r')'
                r'(?::[0-9]{1,5})?'  # 可选端口
            r')/'
        r')?'
        # 仓库路径（必需）
        r'(?P<repository>'
            r'[a-z0-9]+(?:[._-][a-z0-9]+)*'  # 第一级路径
            r'(?:/[a-z0-9]+(?:[._-][a-z0-9]+)*)*'  # 可选的多级路径
        r')'
        # tag 或 digest（至少需要一个）
        r'(?:'
            r'(?::(?P<tag>[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}))?'  # 可选的 tag
            r'(?:@(?P<digest>sha256:[a-fA-F0-9]{64}))?'  # 可选的 digest
        r')'
        r'$',
        re.IGNORECASE
    )
    
    valid_images = []
    invalid_lines = []
    
    for i, line in enumerate(image_lines, start=2):
        # 移除前后空白
        line = line.strip()
        
        # 跳过空行
        if not line:
            continue
        
        # 跳过注释行（以 # 开头）
        if line.startswith('#'):
            continue
        
        # 检查是否匹配镜像格式
        match = image_pattern.match(line)
        if match:
            tag = match.group('tag')
            digest = match.group('digest')
            
            # 必须至少有 tag 或 digest 之一
            if tag or digest:
                valid_images.append({
                    'line': line,
                    'registry': match.group('registry'),
                    'repository': match.group('repository'),
                    'tag': tag,
                    'digest': digest
                })
            else:
                invalid_lines.append(f"第 {i} 行: {line} (缺少 tag 或 digest)")
        else:
            invalid_lines.append(f"第 {i} 行: {line}")
    
    if not valid_images:
        return False, "没有找到有效的镜像", 0
    
    if invalid_lines:
        error_msg = "以下行不符合镜像格式:\n" + "\n".join(invalid_lines[:5])
        if len(invalid_lines) > 5:
            error_msg += f"\n... 还有 {len(invalid_lines) - 5} 行错误"
        return False, error_msg, len(valid_images)
    
    # 统计信息
    tag_count = sum(1 for img in valid_images if img['tag'])
    digest_count = sum(1 for img in valid_images if img['digest'])
    
    stats = []
    if tag_count > 0:
        stats.append(f"{tag_count} 个使用 tag")
    if digest_count > 0:
        stats.append(f"{digest_count} 个使用 digest")
    
    message = f"找到 {len(valid_images)} 个有效镜像"
    if stats:
        message += f" ({', '.join(stats)})"
    
    return True, message, len(valid_images)


def write_output(key, value):
    """写入 GitHub Actions 输出"""
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a', encoding='utf-8') as f:
            # 处理多行值
            if '\n' in str(value):
                delimiter = f"EOF_{key}_{os.getpid()}"
                f.write(f"{key}<<{delimiter}\n")
                f.write(str(value))
                f.write(f"\n{delimiter}\n")
            else:
                f.write(f"{key}={value}\n")
    else:
        # 本地测试模式
        print(f"{key}={value}")


def main():
    if len(sys.argv) < 2:
        print("Usage: check_image_format.py <issue_body>", file=sys.stderr)
        sys.exit(1)
    
    issue_body = sys.argv[1]
    
    # 检查镜像格式
    is_valid, message, image_count = is_valid_image_format(issue_body)
    
    # 输出结果到 GitHub Actions
    write_output('is_image_format', 'true' if is_valid else 'false')
    write_output('check_message', message)
    write_output('image_count', image_count)
    
    # 打印到控制台
    status_emoji = "✅" if is_valid else "❌"
    print(f"{status_emoji} 格式检查: {message}")
    
    # 调试信息
    if not is_valid and image_count > 0:
        print(f"ℹ️  发现 {image_count} 个有效镜像，但存在格式错误")
    
    # 始终返回 0，让 workflow 继续执行
    sys.exit(0)


if __name__ == "__main__":
    main()
