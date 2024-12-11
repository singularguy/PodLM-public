#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# author：samge
# date：2024-10-25 17:13
# describe：配置文件
import os

# 主持人名称
host_speaker = 'leo'
# 嘉宾名称
guest_speaker = 'kunkun'

# 是否需要生成第二次总结性对话
need_second_dialogue = True
# 截断对话的条数，默认为0，表示不进行截断（该配置主要是方便调试使用，截断前几条对话方便加速试听生成效果）
truncate_dialogue_count = 0
# 储存所有合成记录的json文件路径
task_list_file = "task_list.json"
# 合并音频后是否删除原始音频
delete_original_audio = True

# 模型请求地址，这里默认配置了智谱（https://open.bigmodel.cn/）的API，可替换为OpenAI或其他供应商的API
api_url = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'
# 模型请求key
api_key = 'your_api_key'
# 模型名称
model = 'glm-4-plus'
    
# 【必选】获取TTS服务地址 - GET请求 - 请替换为您的TTS服务地址，例如 GPT-SoVITS、F5 TTS、其他在线TTS
def get_tts_url(text, anchor_type):
    # anchor_type 为上面 host_speaker 或 guest_speaker 的值
    return f"http://abc.com/tts?text={text}&language=中英混合&anchor_type={anchor_type}"

# 【可选】TTS服务请求头
tts_headers = {
    'Authorization': 'Bearer xxx'
}

# 【可选】获取TTS服务请求头，方便自定义tts api鉴权
def get_tts_headers():
    return tts_headers


# 获取任务输出的文件路径
def get_task_file(task_id, sub_file = None):
    _dir = os.path.join("output", task_id)
    os.makedirs(_dir, exist_ok=True)
    _path = os.path.join(_dir, sub_file) if sub_file else _dir
    return _path