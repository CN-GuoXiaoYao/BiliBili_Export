# B站缓存工具箱 (By 郭逍遥)

[![GitHub](https://img.shields.io/github/license/CN-GuoXiaoYao/Bilibili_Export)](LICENSE) [![Python Version](https://img.shields.io/badge/python-3.10+-blue)](https://www.python.org/downloads/) [![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](https://github.com/CN-GuoXiaoYao/BiliBili_Export/actions)

---

## 📌 项目简介
B站缓存工具箱是一个多功能的B站缓存工具，包含视频下载、缓存重载、文件合并及系统设置四大核心功能。基于yutto开发，采用图形化界面操作，极大简化B站资源获取与管理流程。

<strong>注意:工具还是会有一些BUG，大家可以根据自己的情况进行修改完善</strong>

软件截图（工具箱+手机App）
<table>
  <tr>
  <td><img src="https://github.com/CN-GuoXiaoYao/BiliBili_Export/blob/56346ea8d593d07a785f3128efd10b41af11b431/Photo/1.png" 
       alt="工具箱" 
       style="width: 750px; border-radius: 8px;"></td>
       
  <td><img src="https://github.com/CN-GuoXiaoYao/BiliBili_Export/blob/56346ea8d593d07a785f3128efd10b41af11b431/Photo/2.jpg" 
       alt="手机缓存工具" 
       style="width: 200px; border-radius: 8px;"></td>
</tr>
</table>

---

## 🔧 功能概览
### ❖ 视频下载
- 支持通过BV号/AV号下载视频
- 提供从360P到8K全分辨率选项(根据实际分辨率为主)
- 合集视频批量下载支持
- 自动检测下载进度

### ❖ 缓存重载
- 支持电脑/手机缓存文件
- 多线程加速重载过程
- 可自定义画质参数

### ❖ 文件合并
- 快速合并.m4s视频片段
- 支持电脑/手机.m4s片段文件
- 支持自定义输出路径与文件名

### ❖ 系统设置
- 缓存根目录配置
- 输出目录设置
- SESSDATA凭证管理
- 下载记录查询

---

```bash
# 文件说明
主要:
BiliBili_Export/
├── gui_app.py      ---GUI脚本
├── download_module.py      ---下载脚本
├── merge_module.py      ---合并脚本
├── reload_module.py      ---重载脚本
├── search_module.py      ---搜索脚本
└── 开始运行.bat      ---运行脚本
其他
└──BilibiliExport.app      ---手机缓存文件名导出App
```

---

## ⚙️ 安装指南
### ❖ 环境要求
- Python 3.10+ 
- Windows操作系统

### ❖ 安装步骤
```bash
下载发布的正式版，然后解压
双击 开始运行.bat 即可下载所需依赖并运行
(会自动下载所需要的yutto和各种依赖)

如果下载缓慢，可以使用以下命令切换国内镜像源下载依赖：
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

---

## 📝 使用教程

### ❖ 视频下载
1. 打开"视频下载"标签页
2. 输入B站视频URL或AV/BV号
3. 选择画质等级（推荐720P）
4. 勾选"下载合集"（如需下载系列视频）
5. 点击"开始下载"
   - 进度条实时显示下载进度
   - 点击"停止下载"可中断当前任务

### ❖ 缓存重载
1. 选择设备类型（电脑/手机）
2. 配置画质参数
3. 设置并发线程数（默认1线程）
4. 点击"开始重载"
   - 手机模式需先选择缓存文件
   - 进度条显示重载进度

### ❖ 文件合并
1. 分别选择视频和音频文件
2. 配置输出路径与文件名
3. 点击"开始合并"
   - 合并完成后自动清除临时文件
   - 成功后弹出保存路径提示

### ❖ 系统设置
1. 配置缓存根目录（必填项）
2. 设置输出目录（默认当前目录）
3. 填写SESSDATA凭证(不知道怎么获得的话请自行搜索)
4. 点击"保存配置"
   - 可通过"打开下载记录"查看历史记录

---

## ⚠️ 注意事项
1. **AV号兼容性**：若遇到下载失败，请优先使用对应的BV号
2. **权限问题**：确保输出目录具有写入权限
3. **手机缓存**：需提前使用提供的APP导出手机缓存文件名至电脑(手机的缓存文件名其实是AV号，电脑不是)
4. **线程控制**：过高线程可能导致系统负载过高
5. **错误日志**：所有异常都会记录到`errors.log`文件
6. **搜索和下载记录**： 重载是通过download标记文件来判断文件下载的，搜索也是搜索的这个标记文件
   
   <strong>Tip:</strong>如果需要xml格式弹幕转换ass格式，可以搜索一下这个工具:[Danmaku2ASS](https://github.com/m13253/danmaku2ass)

---

## 💰 支持作者
如果您觉得本工具对您有帮助，可以给作者B站充电或者在爱发电支持作者：

[BiliBili](https://space.bilibili.com/504668072)
[爱发电](https://afdian.com/a/guoxiaoyao)

---

## 🐞 Bug提交
如发现任何问题，请通过Issues页面提交：
[提交Bug](https://github.com/CN-GuoXiaoYao/BiliBili_Export/issues/new?assignees=&labels=bug&template=bug_report.md&title=%5BBug%5D+)

---

## 📄 许可协议
本项目采用GNU3.0开源协议，详情见[LICENSE](LICENSE)文件。

---

## 👨💻 开发者
郭逍遥 - [GitHub](https://github.com/CN-GuoXiaoYao) | [B站主页](https://space.bilibili.com/504668072)  |  [CSDN](https://blog.csdn.net/qq_58742026)

---

感谢支持~
> 版本：v1.0
