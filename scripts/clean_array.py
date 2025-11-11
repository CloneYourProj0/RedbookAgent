#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据清洗函数 - 直接处理数组
==========================================

用法示例：
---------
from clean_array import clean_xsec_tokens

# 传入数组
cleaned_array = clean_xsec_tokens(your_array)

说明：
-----
这个函数专门处理 structuredContent.result 数组
数组中的每个元素是一个对象，可能是 note 或其他类型

功能：
-----
对于每个 note 对象：
- 删除 noteCard.user.xsecToken
- 保留顶层的 xsecToken

参数：
-----
data_array : list
    包含多个对象的数组，每个对象都有 modelType 字段

返回值：
-------
list
    清洗后的数组（删除了重复的 xsecToken）
"""

import json


def clean_xsec_tokens(data_array):
    """
    清洗数组中的重复xsecToken

    Args:
        data_array: 数组，包含多个对象

    Returns:
        清洗后的数组
    """
    if not isinstance(data_array, list):
        raise TypeError("输入必须是数组！")

    cleaned_count = 0

    # 遍历数组中的每个元素
    for item in data_array:
        # 只处理 note 类型的对象
        if isinstance(item, dict) and item.get('modelType') == 'note':
            # 检查 noteCard 和 user 是否存在
            if 'noteCard' in item and 'user' in item['noteCard']:
                user = item['noteCard']['user']

                # 如果用户对象有 xsecToken，就删除它
                if 'xsecToken' in user:
                    del user['xsecToken']
                    cleaned_count += 1
                    print(f"✓ 已删除 xsecToken (对象ID: {item.get('id', 'N/A')[:10]}...)")

    print(f"\n📊 清洗完成: 共删除了 {cleaned_count} 个重复的 xsecToken")
    return data_array


def clean_json_string(json_string):
    """
    清洗JSON字符串中的重复xsecToken

    适用于处理 content 数组中的字符串

    Args:
        json_string: JSON字符串

    Returns:
        清洗后的JSON字符串
    """
    try:
        # 解析JSON字符串
        obj = json.loads(json_string)

        # 如果是note类型，删除user.xsecToken
        if isinstance(obj, dict) and obj.get('modelType') == 'note':
            if 'noteCard' in obj and 'user' in obj['noteCard']:
                user = obj['noteCard']['user']
                if 'xsecToken' in user:
                    del user['xsecToken']
                    print(f"✓ 已删除字符串中的 user.xsecToken")

        # 转换回JSON字符串
        return json.dumps(obj, ensure_ascii=False)
    except json.JSONDecodeError:
        print("⚠ 无法解析JSON字符串")
        return json_string


# ==================== 使用示例 ====================

if __name__ == "__main__":
    # 示例1: 处理对象数组
    print("示例1: 处理对象数组")
    print("-" * 50)

    # 模拟一个数组（类似structuredContent.result）
    example_array = [
        {
            "id": "note001",
            "modelType": "note",
            "xsecToken": "top_level_token_1",
            "noteCard": {
                "user": {
                    "nickName": "用户1",
                    "xsecToken": "user_token_1"  # 这个会被删除
                }
            }
        },
        {
            "id": "note002",
            "modelType": "note",
            "xsecToken": "top_level_token_2",
            "noteCard": {
                "user": {
                    "nickName": "用户2",
                    "xsecToken": "user_token_2"  # 这个也会被删除
                }
            }
        },
        {
            "id": "rec001",
            "modelType": "rec_query"  # 这个类型不会被处理
        }
    ]

    # 调用清洗函数
    cleaned = clean_xsec_tokens(example_array)

    # 查看结果
    print("\n清洗前:")
    print(json.dumps(example_array, ensure_ascii=False, indent=2))

    print("\n清洗后:")
    print(json.dumps(cleaned, ensure_ascii=False, indent=2))

    # 示例2: 处理JSON字符串
    print("\n\n示例2: 处理JSON字符串")
    print("-" * 50)

    json_str = '{"id":"note003","modelType":"note","xsecToken":"token3","noteCard":{"user":{"nickName":"用户3","xsecToken":"user_token_3"}}}'
    print(f"原始字符串: {json_str}")

    cleaned_str = clean_json_string(json_str)
    print(f"清洗后: {cleaned_str}")
