import requests

'''
这个脚本是通过AV号获取BV号的示例，通过调用B站的API来得到视频信息
'''

def av2bv_via_api(av_id):
    api_url = f"https://api.bilibili.com/x/web-interface/view?aid={av_id}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Referer': 'https://www.bilibili.com/'
    }

    try:
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()

        data = response.json()
        if data.get('code') != 0:
            return {'error': data.get('message', '未知错误')}

        video_info = data.get('data', {})
        return {
            'title': video_info.get('title', '无标题'),
            'bv': video_info.get('bvid', '未找到BV号')
        }

    except requests.exceptions.RequestException as e:
        return {'error': f'网络请求失败: {str(e)}'}
    except ValueError:
        return {'error': 'API响应格式异常'}


# 使用示例
av_number = input("请输入AV号（例如：2）: ").strip('avAV')
result = av2bv_via_api(av_number)

if 'error' in result:
    print(f"错误：{result['error']}")
else:
    print(f"视频标题：{result['title']}")
    print(f"对应BV号：{result['bv']}")