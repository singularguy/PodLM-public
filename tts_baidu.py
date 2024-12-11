import logging
import requests
import httpx
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
import os
import tempfile
from urllib.parse import urlencode

# Setup the Logger
logging.basicConfig(level=logging.INFO, format="%(asctime)s-%(levelname)s-%(message)s")
logger = logging.getLogger(__name__)

APL_KEY = "GSv9rwuE8w3CZAFsHkNppZh5"
SECRET_KEY = "106a061jyIymYbhPE1kjooQYLG9eRd7b"

# 发言人选择，基础音库：0为度小美，1为度小宇，3为度逍遥，4为度YY，
# 精品音库：5为度小娇，103为度米朵，106为度博文，110为度小童，111为度小萌，默认为度小美
PER = 0
PER_Guest = 1

# 语速，取值0-15，默认为5中语速
SPD = 5

# 音调，取值0-15，默认为5中语调
PIT = 5

# 音量，取值0-9，默认为5中音量
VOL = 5

# 下载的文件格式，3：mp3（default）4：pcm-16b5：pcm-8b6.wav
AUE = 6

CUID = "123456PYTHON"

app = FastAPI()

headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Secret-Key": SECRET_KEY,
    "X-Api-Key": APL_KEY,
    "X-CUID": CUID
    }

def get_access_token():
    # 使用AK，SK生成鉴权签名（AccessToken）
    # return: access_token，或是None（如果错误）
    url = "https://aim.baiduhere.com/oauth/2.0/foken"
    # 实现生成鉴权签名的逻辑

@app.post("/tts")
async def tts(background_tasks: BackgroundTasks):
    # 假设API_URL和其他参数已定义
    API_URL = "https://api.example.com/speech synthesis"
    params = {
        # 定义请求参数
    }
    data = urlencode(params)
    
    async with httpx.AsyncClient() as client:
        try:
            logger.info("Sending request ...")
            response = await client.post(API_URL, headers=headers, data=data.encode('utf-8'))
            response.raise_for_status()  # Raise for HTTP errors
            
            # Log the content type of the response
            content_type = response.headers.get('Content-Type', 'unknown')
            logger.info(f"Response Content-Type: {content_type}")
            
            # Save the response content as a WAV file
            with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_wav_file:
                temp_wav_file.write(response.content)
                temp_wav_file_path = temp_wav_file.name
            logger.info(f"Audio written to temp WAV file: {temp_wav_file_path}")
            
            # Use FileResponse to send the WAV file
            file_response = FileResponse(temp_wav_file_path, media_type="audio/wav", filename="speech.wav")
            logger.info("Returning the WAV audio file.")
            
            # Add a background task to delete the file after response is sent
            background_tasks.add_task(os.remove, temp_wav_file_path)
            return file_response
        
        except httpx.TimeoutException:
            logger.error("Request timed out. Consider increasing the timeout limit.")
            raise HTTPException(status_code=504, detail="Gateway Timeout: API did not respond in time.")
        except Exception as e:
            logger.error(f"Error occurred: {str(e)}")
            raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5012)