#!/usr/bin/env python3
"""
Secret scanner for OpenClaw backup
Detects and sanitizes API keys, tokens, passwords, and other sensitive data
"""

import os
import re
import json
import sys
from pathlib import Path

# Common secret patterns
SECRET_PATTERNS = {
    'openai_api_key': r'sk-(proj-)?[a-zA-Z0-9]{48}',
    'anthropic_api_key': r'sk-ant-[a-zA-Z0-9]{48}',
    'generic_api_key': r'[a-zA-Z0-9]{32,64}',
    'telegram_bot_token': r'[0-9]{8,10}:[a-zA-Z0-9_-]{35}',
    'github_token': r'gh[pors]_[a-zA-Z0-9]{36}',
    'aws_access_key': r'AKIA[0-9A-Z]{16}',
    'aws_secret_key': r'[a-zA-Z0-9+/]{40}',
    'database_url': r'(mongodb|postgresql|mysql|redis)://[^:]+:[^@]+@',
    'email_password': r'"password":\s*"[^"]+"',
    'slack_token': r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24}',
    'discord_token': r'[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}',
}

def scan_file_for_secrets(filepath):
    """Scan a file for potential secrets"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        found_secrets = []
        for secret_type, pattern in SECRET_PATTERNS.items():
            matches = re.findall(pattern, content)
            if matches:
                found_secrets.append({
                    'type': secret_type,
                    'count': len(matches),
                    'examples': matches[:3]  # Show first 3 examples
                })
        
        return found_secrets
    except Exception as e:
        return [{'type': 'error', 'message': str(e)}]

def sanitize_file(input_path, output_path):
    """Create a sanitized copy of a file"""
    try:
        with open(input_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        # Apply sanitization
        sanitized = content
        
        # Replace secrets with placeholders
        sanitized = re.sub(r'sk-(proj-)?[a-zA-Z0-9]{48}', '[OPENAI_API_KEY]', sanitized)
        sanitized = re.sub(r'sk-ant-[a-zA-Z0-9]{48}', '[ANTHROPIC_API_KEY]', sanitized)
        sanitized = re.sub(r'[0-9]{8,10}:[a-zA-Z0-9_-]{35}', '[TELEGRAM_BOT_TOKEN]', sanitized)
        sanitized = re.sub(r'gh[pors]_[a-zA-Z0-9]{36}', '[GITHUB_TOKEN]', sanitized)
        sanitized = re.sub(r'AKIA[0-9A-Z]{16}', '[AWS_ACCESS_KEY]', sanitized)
        sanitized = re.sub(r'[a-zA-Z0-9+/]{40}', '[AWS_SECRET_KEY]', sanitized)
        sanitized = re.sub(r'(mongodb|postgresql|mysql|redis)://[^:]+:[^@]+@', r'\1://[USER]:[PASSWORD]@', sanitized)
        sanitized = re.sub(r'"password":\s*"[^"]+"', '"password": "[PASSWORD]"', sanitized)
        
        # Write sanitized content
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(sanitized)
        
        return True, "File sanitized successfully"
    except Exception as e:
        return False, f"Error sanitizing file: {str(e)}"

def scan_directory(directory_path):
    """Scan a directory for secrets"""
    results = {
        'directory': directory_path,
        'files_scanned': 0,
        'secrets_found': 0,
        'files_with_secrets': [],
        'total_secrets_by_type': {}
    }
    
    for root, dirs, files in os.walk(directory_path):
        for file in files:
            filepath = os.path.join(root, file)
            
            # Skip binary files and large files
            if file.endswith(('.png', '.jpg', '.jpeg', '.gif', '.pdf', '.zip', '.tar', '.gz')):
                continue
            
            try:
                file_size = os.path.getsize(filepath)
                if file_size > 10 * 1024 * 1024:  # Skip files > 10MB
                    continue
            except:
                continue
            
            secrets = scan_file_for_secrets(filepath)
            results['files_scanned'] += 1
            
            if secrets and not (len(secrets) == 1 and secrets[0]['type'] == 'error'):
                results['secrets_found'] += 1
                file_result = {
                    'path': filepath,
                    'secrets': secrets
                }
                results['files_with_secrets'].append(file_result)
                
                # Update counts by type
                for secret in secrets:
                    if secret['type'] != 'error':
                        results['total_secrets_by_type'][secret['type']] = \
                            results['total_secrets_by_type'].get(secret['type'], 0) + secret['count']
    
    return results

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python secret_scanner.py <directory_to_scan>")
        sys.exit(1)
    
    directory = sys.argv[1]
    if not os.path.exists(directory):
        print(f"Directory not found: {directory}")
        sys.exit(1)
    
    print(f"Scanning directory: {directory}")
    results = scan_directory(directory)
    
    print(f"\nScan Results:")
    print(f"Files scanned: {results['files_scanned']}")
    print(f"Files with secrets: {results['secrets_found']}")
    
    if results['secrets_found'] > 0:
        print(f"\nSecret types found:")
        for secret_type, count in results['total_secrets_by_type'].items():
            print(f"  {secret_type}: {count}")
        
        print(f"\nFiles with secrets (first 10):")
        for file_result in results['files_with_secrets'][:10]:
            print(f"\n  {file_result['path']}:")
            for secret in file_result['secrets']:
                if secret['type'] != 'error':
                    print(f"    - {secret['type']}: {secret['count']} found")
                    if 'examples' in secret and secret['examples']:
                        print(f"      Examples: {secret['examples'][:2]}")
    else:
        print("No secrets found!")

if __name__ == "__main__":
    main()