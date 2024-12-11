## 项目配置和运行指南

### 1. 配置依赖

确保您的系统已安装Python (推荐使用Python 3.11.5版本)，例如使用conda创建一个python环境并激活环境：

```shell
conda create -n podlm-public python=3.11.5 -y

conda activate podlm-public
```

安装项目依赖：

```shell
pip install -r requirements.txt
```

### 2. 配置API URL和密钥

将`config.demo.py`配置文件复制到`config.py`，并根据注释说明修改`config.py`中的配置项：

```shell
cp config.demo.py config.py
```

在`config.py`中，将以下配置替换为您的API URL、密钥和模型名称：

```python
# 模型请求地址，这里默认配置了智谱（https://open.bigmodel.cn/）的API，可替换为OpenAI或其他供应商的API
api_url = 'https://open.bigmodel.cn/api/paas/v4/chat/completions'
# 模型请求key
api_key = 'your_api_key'
# 模型名称
model = 'glm-4-flash'
# 主机说话者声音
voice = 'xxxx'
```

### 3. 配置TTS服务和地址

在`config.py`中，配置TTS服务地址和请求头：

```python
# 获取TTS服务地址 - GET请求 - 请替换为您的TTS服务地址，例如 GPT-SoVITS、F5 TTS、其他在线TTS
def get_tts_url(text, anchor_type):
    # anchor_type 为上面 host_speaker 或 guest_speaker 的值
    return f"http://abc.com/tts?text={text}&language=中英混合&anchor_type={anchor_type}"

# 【可选】TTS服务请求头
tts_headers = {
    'Authorization': 'Bearer xxx'
}
```

### 4. 复制TTS服务文件

将`tts_baidu.py`复制到项目中，以便使用TTS服务。

### 5. 创建任务列表文件

创建一个名为`task_list.json`的文件，并按照以下格式添加任务：

```json
[
    {
        "taskId": "task_1",
        "url": "https://example.com/page1",  # 将url替换成需要转换测网页地址
        "status": "pending",
        "progress": "等待处理",
        "createdAt": "2023-10-01T12:00:00",
        "updatedAt": "2023-10-01T12:00:00"
    }
]
```

### 6. 启动服务器

启动`server.py`、`api.py`和`tts_baidu.py`：

```shell
python server.py
```

```shell
python api.py
```

```shell
python tts_baidu.py
```

现在，您的项目应该已经配置好并可以运行了。您可以通过访问`http://localhost:8811`来使用API，并通过`server.py`和`server_pro.py`来处理任务。