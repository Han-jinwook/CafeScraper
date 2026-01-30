#!/usr/bin/env python3
"""
이모지를 텍스트로 교체하는 스크립트
"""
import re

def fix_emojis():
    with open('app/scraper/naver.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 이모지를 텍스트로 교체
    replacements = {
        '✅': '[SUCCESS]',
        '❌': '[ERROR]', 
        '🔄': '[INFO]',
        '⚠️': '[WARN]'
    }
    
    for emoji, text in replacements.items():
        content = content.replace(emoji, text)
    
    with open('app/scraper/naver.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print('이모지 교체 완료')

if __name__ == "__main__":
    fix_emojis()

