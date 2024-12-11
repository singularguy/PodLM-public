import tempfile
import time
import json
import os
import ffmpeg
import requests
import threading
from datetime import datetime
from bs4 import BeautifulSoup
import re
import config

def log(message):
    print(f"[{datetime.now().isoformat()}] {message}")

def fetch_url_content(url, task_id):
    try:
        content_file = config.get_task_file(task_id, 'content.txt')
        if os.path.exists(content_file) and os.path.getsize(content_file) > 0:
            log(f"发现已存在的内容文件: {content_file}")
            with open(content_file, 'r', encoding='utf-8') as f:
                text_content = f.read()
            log(f"已从现有文件加载内容，长度: {len(text_content)} 字符")
            
            # 从已存在的文件中读取标题
            title_file = config.get_task_file(task_id, 'title.txt')
            if os.path.exists(title_file):
                with open(title_file, 'r', encoding='utf-8') as f:
                    title = f.read().strip()
            else:
                title = "无标题"
        else:
            log(f"正在获取页面内容: {url}")
            response = requests.get(url)
            response.raise_for_status()
            
            # 保存原始HTML到old.html文件
            with open(config.get_task_file(task_id, 'old.html'), 'w', encoding='utf-8') as f:
                f.write(response.text)
            log("原始HTML已保存到old.html文件")
            
            soup = BeautifulSoup(response.text, 'html.parser')
        
            text_content = soup.get_text()
            # 删除text_content中的换行符
            text_content = text_content.replace('\n', ' ').replace('\r', '')
        
            # 保存纯文本内容到content.txt文件
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(text_content)
            log("纯文本内容已保存到content.txt文件")
        
            # 提取并保存标题到title.txt文件
            title_match = re.search(r'<title>(.*?)</title>', response.text, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1) if title_match else ""
        
            if not title:
                if len(text_content) < 4:
                    log("获取页面内容失败或内容为空，请重新提交")
                    title = "获取页面内容失败或内容为空，请重新提交"
                else:
                    log("标题为空，正在调用LLM生成播客标题")
                    title = generate_podcast_title(text_content)
        
            with open(config.get_task_file(task_id, 'title.txt'), 'w', encoding='utf-8') as f:
                f.write(title)
            log("标题已保存到title.txt文件")
        
        log(f"成功获取页面内容，长度: {len(text_content)} 字符")
        return text_content, title
    except Exception as e:
        log(f"获取URL内容失败: {str(e)}")
        return '',''
        raise

def generate_podcast_title(content):
    def llm_request():
        api_url = config.api_url
        api_key = config.api_key
        model = config.model
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        data = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': '你是一个播客标题生成器，请根据给定的内容生成一个吸引人的播客标题，标题需要有内涵一点。不要输出任何emoji符号，严禁输出《》：等符号，严禁输出《》：等符号，严禁输出《》：等符号。'},
                {'role': 'user', 'content': f"请为以下内容生成一个播客标题:\n{content}"} 
            ]
        }
        response = requests.post(api_url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content'].strip()
        else:
            raise ValueError('API返回的数据格式不正确')

    for attempt in range(2):
        try:
            title = llm_request()
            log(f"成功生成播客标题: {title}")
            return title
        except Exception as e:
            log(f'LLM请求失败 (尝试 {attempt+1}/2): {str(e)}')
            if attempt == 1:  # 最后一次尝试失败
                log("所有LLM请求尝试均失败，使用默认标题")
                return "无标题"

    return "无标题"  # 这行代码实际上永远不会执行，因为上面的循环会处理所有情况

def execute_task(task):
    task_id = task['taskId']
    url = task['url']
    
    log(f"开始执行任务 {task_id}")
    
    # 更新任务状态
    update_task_status(task_id, 'processing', '正在获取页面内容')
    
    # 获取页面内容
    text_content, title = fetch_url_content(url, task_id)
    if len(text_content) < 4:
        log(f"获取页面内容失败或内容为空，URL: {url}")
        update_task_status(task_id, 'failed', '获取页面内容失败或内容为空，请重新提交')
        return
    if "当前环境异常，完成验证后即可继续访问" in text_content:
        log(f"检测到页面需要验证，URL: {url}")
        update_task_status(task_id, 'failed', '请求URL失败，请重试')
        return
    log(f"成功获取页面内容，长度: {len(text_content)} 字符")
    
    # 调用 LLM 接口生成对话内容
    update_task_status(task_id, 'processing', '正在生成对话内容')
    log("正在调用 LLM 接口生成对话内容")
    dialogue = generate_dialogue(text_content)
    log(f"成功生成对话内容，共 {len(dialogue)} 条对话")
    
    # 保存对话内容
    dialogue_file = config.get_task_file(task_id, 'dialogue.json')
    log(f"正在保存对话内容到文件: {dialogue_file}")
    with open(dialogue_file, 'w') as f:
        json.dump(dialogue, f, indent=4)
    log("对话内容保存成功")
    
    # 调用 TTS 接口合成音频
    update_task_status(task_id, 'processing', '正在合成音频')
    log("正在调用 TTS 接口合成音频")
    audio_files = generate_audio(dialogue, task_id)
    if not audio_files:
        update_task_status(task_id, 'failed', 'TTS音频生成失败')
        return
    log(f"成功生成 {len(audio_files)} 个音频文件")
    
    # 合并音频文件
    update_task_status(task_id, 'processing', '正在合并音频文件')
    log("开始合并音频文件")
    merge_audio_files(audio_files, task_id)
    log("音频文件合并完成")
    
    # 更新任务状态为完成
    update_task_status(task_id, 'completed', '任务完成')
    log(f"任务 {task_id} 执行完成")
    
    # 调用新函数上传到小宇宙
    upload_to_xiaoyuzhou(task_id)

def upload_to_xiaoyuzhou(task_id):
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.edge.options import Options
    import time
    import os
    log(f"开始上传任务 {task_id} 到小宇宙")

    # 自动下载并设置Edge驱动
    from selenium import webdriver
    from selenium.webdriver.edge.service import Service
    from webdriver_manager.microsoft import EdgeChromiumDriverManager

    # 设置Edge浏览器选项
    edge_options = Options()
    edge_options.add_argument(f"user-data-dir=C:\\edge")

    # 使用EdgeChromiumDriverManager自动下载并设置驱动
    service = Service(EdgeChromiumDriverManager().install())

    # 初始化Edge浏览器
    driver = webdriver.Edge(service=service, options=edge_options)

    try:
        # 打开小宇宙页面
        driver.get("https://podcaster.xiaoyuzhoufm.com/podcasts/66fef2c7f03810fc2f505b0d/contents-management/episodes")

        # 等待"主页"元素出现
        while True:
            try:
                element = driver.find_element(By.XPATH, '//span[@class="jsx-3385323943 label active"]')
                if element.text == "主页":
                    driver.get("https://podcaster.xiaoyuzhoufm.com/podcasts/66fef2c7f03810fc2f505b0d/contents-management/episodes")
                    break
                
                element = driver.find_element(By.XPATH, '//h2[@class="css-1dlp2vs"]')
                if element.text == "内容管理":
                    driver.get("https://podcaster.xiaoyuzhoufm.com/podcasts/66fef2c7f03810fc2f505b0d/contents-management/episodes")
                    break
            except:
                pass

        time.sleep(2)
        # 点击上传按钮
        driver.find_element(By.XPATH, '//div[@class="css-k4ekfx e1ab6r9u3"]').click()
        time.sleep(2)

        # 等待标题输入框出现
        try:
            title_input = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.XPATH, '//input[@class="css-19crfhb css-1r2ttr7 e1ab6r9u7"]'))
            )
        except Exception as e:
            log(f"小宇宙有点小问题 {str(e)}")
            return

        # 输入标题
        with open(config.get_task_file(task_id, 'title.txt'), 'r', encoding='utf-8') as f:
            title = f.read().strip()
        title_input.send_keys(title)
        time.sleep(2)

        # 上传音频文件
        upload_input = driver.find_element(By.XPATH, '//input[@id="upload"]')
        upload_input.send_keys(os.path.abspath(config.get_task_file(task_id, f"{task_id}.wav")))
        time.sleep(2)

        # 生成内容大纲
        with open(config.get_task_file(task_id, 'content.txt'), 'r', encoding='utf-8') as f:
            content = f.read()
        outline = generate_outline(content)
        print('outline',outline)
        time.sleep(2)

        # 输入内容大纲
        try:
            editor = driver.find_element(By.XPATH, '//div[@class="notranslate public-DraftEditor-content"]')
            editor.send_keys(outline)
            time.sleep(2)
        except Exception as e:
            log(f"大纲输入有点问题")

        time.sleep(2)
        # 点击发布设置
        driver.find_element(By.XPATH, '//div[@class="css-1079hn7"]//div[@class="css-1i5dn6c"]').click()
        time.sleep(2)
        # 等待发布按钮可点击并点击
        start_time = time.time()
        while time.time() - start_time < 90:
            try:
                # 等待"发布成功"元素出现
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, '//div[@class="css-13dmsdw css-11conra e1ab6r9u4"]'))
                )
                # 点击发布按钮
                publish_button = driver.find_element(By.XPATH, '//div[@class="css-1079hn7"]//div[@class="css-k4ekfx e1ab6r9u3"]')
                publish_button.click()
                log("成功点击发布按钮")
                break
            except:
                time.sleep(2)
        else:
            log("等待60秒后仍未能成功发布，结束任务")

    except Exception as e:
        log(f"上传到小宇宙过程中出错: {str(e)}")
    finally:
        # 关闭浏览器
        driver.quit()
        pass
    
    log(f"完成上传任务 {task_id} 到小宇宙")

def generate_outline(content):
    log("开始生成内容大纲")
    
    def llm_request(prompt):
        api_url = config.api_url
        api_key = config.api_key
        model = config.model
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        data = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': '你是一个专业的播客内容编辑，请根据给定的内容生成一个简洁的播客内容大纲。'},
                {'role': 'user', 'content': prompt}
            ]
        }
        response = requests.post(api_url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        if 'choices' in result and len(result['choices']) > 0:
            return result['choices'][0]['message']['content'].strip()
        else:
            raise ValueError('API返回的数据格式不正确')

    prompt = f"请为以下内容生成一个简洁的播客内容大纲，包括3-5个主要点：\n\n{content}"

    for attempt in range(3):
        try:
            outline = llm_request(prompt)
            log("成功生成内容大纲")
            # 替换outline中的**和###
            outline = outline.replace('**', '').replace('### ', '').replace('###', '').replace('#', '').replace('*', '')
            return outline
        except Exception as e:
            log(f'生成内容大纲失败 (尝试 {attempt+1}/3): {str(e)}')
            if attempt == 2:  # 最后一次尝试失败
                log("所有生成内容大纲的尝试均失败，使用默认大纲")
                return " "

    return " "  # 这行代码实际上永远不会执行，因为上面的循环会处理所有情况

def tts_request(text, anchor_type):
    url = config.get_tts_url(text, anchor_type)
    for _ in range(3):
        try:
            response = requests.get(url, timeout=120, headers=config.get_tts_headers())
            response.raise_for_status()
            return response.content
        except requests.RequestException as e:
            log(f"TTS请求失败: {str(e)}，正在重试...")
    log("TTS请求失败3次，放弃尝试")
    return None

def generate_audio(dialogue, task_id):
    log(f"开始为任务 {task_id} 生成音频")
    audio_files = []
    temp_dir = task_id
    status_file = config.get_task_file(temp_dir, 'status.json')
    total_lines = len(dialogue)
    
    for i, item in enumerate(dialogue):
        anchor_type = config.host_speaker if item['role'] == 'host' else config.guest_speaker
        log(f"正在为第 {i+1} 条对话生成音频，角色: {anchor_type}")
        
        # 更新状态文件
        status = {
            "current_line": i + 1,
            "total_lines": total_lines,
            "content": item['content']
        }
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(status, f, ensure_ascii=False, indent=4)
        
        audio_content = tts_request(item['content'], anchor_type)
        if audio_content is None:
            log(f"第 {i+1} 条对话音频生成失败")
            return None
        
        audio_file = config.get_task_file(temp_dir, f"{i:04d}_{item['role']}.wav")
        with open(audio_file, 'wb') as f:
            f.write(audio_content)
        audio_files.append(audio_file)
        log(f"第 {i+1} 条对话音频生成完成: {audio_file}")
    
    log(f"所有音频生成完成，共 {len(audio_files)} 个文件")
    return audio_files

def update_task_status(task_id, status, progress):
    log(f"更新任务 {task_id} 状态: {status}, 进度: {progress}")
    with open(config.task_list_file, 'r+') as f:
        tasks = json.load(f)
        for task in tasks:
            if task['taskId'] == task_id:
                task['status'] = status
                task['progress'] = progress
                task['updatedAt'] = datetime.now().isoformat()
                break
        f.seek(0)
        json.dump(tasks, f, indent=4)
        f.truncate()
    log(f"任务 {task_id} 状态更新完成")

def generate_dialogue(text_content):
    api_url = config.api_url
    api_key = config.api_key
    model = config.model
    log("开始生成对话内容")
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    all_content = []

    # 第一次 LLM 请求
    if config.need_second_dialogue:
        data = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': f'你是一个播客对话内容生成器,你需要将我给你的内容转换为自然的对话,主持人叫{config.host_speaker}。'+'对话以探讨交流形式,不要问答形式,正式对话开始前需要有引入主题的对话,需要欢迎大家收听本期播客,对话需要更口语化一点日常交流,你输出的内容不要结束对话,后面我还会补充更多对话,一定不能有任何结束性对话,直接结束就行,后面我还会补充内容。总内容字数需要大于10000字。在保证完整性的同时你还需要给我增加补充相关内容,一定要延伸补充,对话不是简单的一问一答,需要在每个发言中都抛出更多的观点和内容知识,需要补充更多的内容,不要使用提问形式使用交流探讨形式。以JSON格式输出,除了json内容不要输出任何提示性内容,直接json输出,不要提示性内容以及任何格式内容,严禁输出 ```json 此类格式性内容,直接输出json即可,格式严格参考 [{"role": "host", "content": "你好"}, {"role": "guest", "content": "你好"}]'},
                {'role': 'user', 'content': f"请将以下内容转换成播客对话,对话内容content不要加身份前缀直接出对话内容即可,内容如下:\n{text_content}"}
            ]
        }
        log("正在发送第一次请求到 LLM API")
        response = requests.post(api_url, headers=headers, json=data)
        if response.status_code == 200:
            log("成功接收第一次 LLM API 响应")
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
                log(f"API 返回的原始内容: {content}")
                try:
                    content = content.replace('```json', '').replace('```', '')
                    dialogue = json.loads(content)
                    all_content.extend(dialogue)
                    log(f"成功解析第一次对话内容，共 {len(dialogue)} 条对话")
                except json.JSONDecodeError as e:
                    log(f"JSON 解析错误: {str(e)}")
                    log("尝试修复 JSON 格式")
                    fixed_content = content.replace("'", '"').replace('\n', '\\n')
                    try:
                        dialogue = json.loads(fixed_content)
                        all_content.extend(dialogue)
                        log(f"修复后成功解析对话内容，共 {len(dialogue)} 条对话")
                    except json.JSONDecodeError as e:
                        log(f"修复后仍然无法解析 JSON: {str(e)}")
                        return []
        else:
            log(f"第一次生成对话内容失败，状态码: {response.status_code}")
            return []

        # 第二次 LLM 请求
        data = {
            'model': model,
            'messages': [
                {'role': 'system', 'content': '你是一位播客内容编辑,我会给你一些参考内容以及你之前生成的播客内容,在这些内容基础上补充对话内容,补充的内容不要跟前的内容产生冲突,并且你只需要输出补充的内容即可,对话需要更口语化一点日常交流,对话不能是简单的一问一答,需要是探讨交流形式,结束总结性需要有总结性对话,总内容字数需要大于10000字。保持内容的完整性,在保证完整性的同时你还需要给我增加补充相关内容,一定要延伸补充,对话不是简单的一问一答应该在每个发言中都抛出更多的观点和内容知识,你需要补充更多的内容,不要使用提问对话的形式,并以JSON格式输出。注意,输出json格式,除了json内容不要输出任何提示性内容,直接json输出,不要提示性内容以及任何格式内容,严禁输出 ```json 此类格式性内容,直接输出json即可,格式参考 [{"role": "host", "content": "你好"}, {"role": "guest", "content": "你好"}]'},
                {'role': 'user', 'content': f"参考内容如下:\n{text_content}。\n你之前的生成的内容：{content}"}
            ]
        }
        log("正在发送第二次请求到 LLM API")
        response = requests.post(api_url, headers=headers, json=data)
        if response.status_code == 200:
            log("成功接收第二次 LLM API 响应")
            result = response.json()
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content'] or ""
                log(f"API 返回的原始内容: {content}")
                try:
                    content = content.replace('```json', '').replace('```', '')
                    dialogue = json.loads(content)
                    all_content.extend(dialogue)
                    log(f"成功解析第二次对话内容，共 {len(dialogue)} 条对话")
                except json.JSONDecodeError as e:
                    log(f"JSON 解析错误: {str(e)}")
                    log("尝试修复 JSON 格式")
                    fixed_content = content.replace("'", '"').replace('\n', '\\n')
                    try:
                        dialogue = json.loads(fixed_content)
                        all_content.extend(dialogue)
                        log(f"修复后成功解析对话内容，共 {len(dialogue)} 条对话")
                    except json.JSONDecodeError as e:
                        log(f"修复后仍然无法解析 JSON: {str(e)}")
        else:
            log(f"第二次生成对话内容失败，状态码: {response.status_code}")

    log(f"总共生成对话内容 {len(all_content)} 条")
    if config.truncate_dialogue_count > 0:
        log(f"截取前 {config.truncate_dialogue_count} 条")
        all_content = all_content[:config.truncate_dialogue_count]
    return all_content


def merge_audio_files(audio_files, task_id):
    log(f"开始合并任务 {task_id} 的音频文件")
    temp_dir = task_id
    output_file = config.get_task_file(temp_dir, f"{task_id}.wav")
    
    # 创建一个临时文件记录音频文件列表
    temp_file_name = '.temp_file_list.txt'
    with open(temp_file_name, 'w') as f:
        for audio_file in audio_files:
            f.write(f"file '{audio_file}'\n")
    try:
        ffmpeg.input(temp_file_name, format='concat', safe=0).output(output_file).overwrite_output().run()
        print(f"音频文件合并完成，输出文件：{output_file}")
    except ffmpeg.Error as e:
        print(f"合并音频文件时出错: {e}")
    finally:
        os.remove(temp_file_name)
        if config.delete_original_audio:
            for audio_file in audio_files:
                os.remove(audio_file)
        
    log(f"音频文件合并完成，输出文件为 {output_file}")

def check_and_execute_incomplete_tasks():
    log("检查未完成的任务")
    try:
        with open(config.task_list_file, 'r') as f:
            tasks = json.load(f)
        
        incomplete_tasks = [task for task in tasks if task['status'] not in ['completed', 'failed']]
        
        if incomplete_tasks:
            log(f"发现 {len(incomplete_tasks)} 个未完成的任务")
            for task in incomplete_tasks:
                log(f"重新执行任务: {task['taskId']}")
                threading.Thread(target=execute_task, args=(task,)).start()
        else:
            log("没有发现未完成的任务")
    except FileNotFoundError:
        log(f"{config.task_list_file} 文件不存在")
    except json.JSONDecodeError:
        log(f"{config.task_list_file} 文件格式错误")
    except Exception as e:
        log(f"检查未完成任务时发生错误: {str(e)}")

def check_new_tasks():
    log("开始检查新任务")
    while True:
        try:
            with open(config.task_list_file, 'r') as f:
                tasks = json.load(f)
            
            for task in tasks:
                if task['status'] == 'pending':
                    log(f"发现新任务: {task['taskId']}")
                    threading.Thread(target=execute_task, args=(task,)).start()
            
            time.sleep(2)
        except Exception as e:
            log(f"检查新任务时发生错误: {e}")
            time.sleep(5)  # 如果发生错误，等待一段时间后重试

if __name__ == '__main__':
    log("启动任务处理服务器...")
    check_and_execute_incomplete_tasks()  # 在启动时检查并执行未完成的任务
    check_new_tasks()  # 继续检查新任务