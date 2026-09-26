import os
import queue
import sys
import threading
import time
import re
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import requests
from playwright.sync_api import sync_playwright
HEADERS = {"User-Agent": "Mozilla** (Windows **; Win64; x64) Apple**it** ""(K**, like Ge**) Chrome** Safari** Edg**"}
HEADLESS = True
MAX_RETRY = 3
WAIT_SEC = 20
TARGET_SITE = "https://**.example.com/"   # ← 请改成你的目标动漫站
PROJECTS = [{"name": "动漫站",   "site": "https://**.example.com/",  "worker_cls": "AnimeWorker",    "ready": True},]
class BaseWorker(threading.Thread):
    def __init__(self, cmd_q, res_q):  # def=定义函数, __init__=构造函数(创建对象时自动调用), self=机器人自己, cmd_q=指令信箱参数, res_q=结果信箱参数
        super().__init__(daemon=True)  # super()=父类(threading.Thread)的引用, .__init__()=初始化线程, daemon=True=窗口关闭时线程一起结束(守护线程)
        self.cmd_q = cmd_q             # self.cmd_q=机器人记住指令信箱(存到自己的属性里备用)
        self.res_q = res_q             # self.res_q=机器人记住结果信箱
        self.running = True            # self.running=上班开关, True=继续干活
        self.playwright = None         # self.playwright=遥控浏览器总管家(先占位None)
        self.browser = None            # self.browser=浏览器对象(先占位None)
        self.context = None            # self.context=浏览器的独立会话(房间)(先占位None)
        self.page = None               # self.page=网页页面对象(先占位None)
    def submit(self, cmd, **kw):       # def=定义函数, submit=方法名(提交指令), cmd=指令名字符串, **kw=可变关键字参数(额外信息如kw=关键词)
        self.cmd_q.put({"cmd": cmd, **kw})  # self.cmd_q=指令信箱, .put()=把字典塞进去, {"cmd":cmd, **kw}=指令字典(含指令名和附加数据)
    def log(self, msg):                # def=定义函数, log=方法名(写日志), msg=要写的文字
        self.res_q.put({"type": "log", "msg": str(msg)})  # self.res_q=结果信箱, .put()=塞入, {"type":"log",...}=日志纸条(窗口收到会显示)
    def run(self):                     # def=定义函数, run=线程入口方法(调用.start()后自动执行)
        if sys.platform == "win32":    # sys.platform=系统名, == "win32"=如果是Windows
            import asyncio             # import=引入, asyncio=异步事件库
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())  # 强制用Proactor事件循环(基于IOCP), 它才支持子进程; 之前用WindowsSelectorEventLoopPolicy会让Playwright启动驱动进程时抛NotImplementedError
        try:                           # try=尝试执行, 出错不崩溃
            self.playwright = sync_playwright().start()  # sync_playwright()=创建总管家, .start()=启动它, 赋给self.playwright
            self.on_start()            # self.on_start()=调用子类的"打开浏览器进网站"方法(多态, 各网站不同)
        except Exception as e:         # except=捕获异常, Exception=所有错误类型, as e=把错误信息存到e
            import traceback           # import=引入, traceback=堆栈跟踪库(能打印出错的具体行号)
            self.log(f"[启动失败] {e}")  # self.log()=记录日志, f"...{e}"=格式化字符串(把e的内容填进去)
            self.log(traceback.format_exc())  # self.log()=记录日志, traceback.format_exc()=把完整出错位置和调用链转成文字(方便排查)
            self.running = False       # self.running=False=关掉上班开关(不再循环)
        while self.running:            # while=循环, self.running=True期间不断执行
            try:                       # try=尝试
                cmd = self.cmd_q.get(timeout=0.2)  # self.cmd_q.get()=从指令信箱取一条, timeout=0.2=等0.2秒没有就抛空异常
            except queue.Empty:        # except=捕获, queue.Empty=信箱空时抛出的异常
                continue               # continue=跳过本次循环回到while开头(继续等指令)
            handler = getattr(self, "do_" + cmd["cmd"], None)  # getattr(对象,名字,默认)=按名字找方法, "do_"+cmd["cmd"]=拼出方法名(如"do_search"), None=找不到时的默认值
            if handler is None:        # if=如果, handler is None=方法不存在
                self.log(f"[未知指令] {cmd['cmd']}")  # 记录日志提示未知指令
                continue               # continue=跳过, 等下一条
            try:                       # try=尝试执行指令
                self.log(f">>> 执行: {cmd['cmd']}")  # 记录"正在执行哪条指令"
                handler(cmd)           # handler(cmd)=调用找到的那个do_xxx方法, 并把指令字典传进去
            except Exception as e:     # except=捕获, 执行指令时出错
                self.log(f"[异常] {e}")  # 记录异常但不让整个程序崩溃
        self.on_exit()                 # self.on_exit()=循环结束(下班)时调用, 关闭浏览器
    def on_start(self):                # def=定义函数, on_start=打开浏览器方法
        raise NotImplementedError      # raise=主动抛出错误, NotImplementedError=未实现错误(提示子类必须覆盖本方法)
    def on_exit(self):                 # def=定义函数, on_exit=退出方法
        try:                           # try=尝试
            self.browser.close()       # self.browser=浏览器对象, .close()=关闭浏览器
        except Exception:              # except=出错就忽略
            pass                       # pass=什么都不做(关不掉就算了)
        try:                           # try=尝试
            self.playwright.stop()     # self.playwright=总管家, .stop()=关闭它
        except Exception:              # except=出错就忽略
            pass                       # pass=什么都不做
class AnimeWorker(BaseWorker):
    def on_start(self):                # def=定义函数, on_start=启动方法(由基类run()调用)
        self.video_target_url = None   # self.video_target_url=装抓到的视频地址(每次清空)
        self.result_locators = []      # self.result_locators=装每个搜索结果的元素句柄列表
        self.ep_locators = []          # self.ep_locators=装每集元素的句柄列表
        self.ep_names = []             # self.ep_names=装每集名字的列表
        self.anime_name = ""           # self.anime_name=当前番剧名
        self.level = "search"          # self.level=初始层级=搜索页
        launch_errors = []             # launch_errors=装每次尝试失败的报错信息(最后一起打印方便排查)
        self.browser = None            # self.browser=浏览器对象, 先清空
        try:                           # try=尝试
            self.browser = self.playwright.chromium.launch(  # self.playwright.chromium=chromium内核, .launch()=启动浏览器
                channel="msedge",      # channel="msedge"=用系统里已安装的Edge(自动找, 无需写路径)
                headless=HEADLESS,     # headless=是否隐藏窗口, 用HEADLESS常量的值(False=显示)
                args=[                 # args=启动附加参数列表
                    '--disable-blink-features=AutomationControlled',  # 关掉自动化的特征标记(防网站识别是机器人)
                    '--disable-infobars',  # 去掉浏览器顶部的"由自动化软件控制"提示条
                    '--start-maximized', ])
        except Exception as e:         # except=捕获方式1失败
            launch_errors.append(f"方式1(msedge)失败: {e}")  # launch_errors.append()=往列表末尾加一条失败原因
        if self.browser is None:       # if=如果方式1没成功
            try:                       # try=尝试
                self.log("msedge 启动失败, 尝试默认chromium...")  # self.log()=记录日志提示切换
                self.browser = self.playwright.chromium.launch(  # .launch()=用默认内核启动
                    headless=HEADLESS, # headless=是否隐藏窗口
                    args=[             # args=启动附加参数列表
                        '--disable-blink-features=AutomationControlled',  # 防识别
                        '--disable-infobars',  # 去提示条
                        '--start-maximized',])
            except Exception as e:     # except=捕获方式2失败
                launch_errors.append(f"方式2(默认chromium)失败: {e}")  # 追加失败原因
        if self.browser is None:       # if=两种方式都失败
            raise RuntimeError("浏览器启动失败: " + " | ".join(launch_errors))  # raise=主动抛异常, RuntimeError=运行时错误, " | ".join(列表)=把失败原因用竖线拼成一句话
        self.context = self.browser.new_context()   # self.browser.new_context()=新建一个独立会话(房间), 存cookie等
        self.context.add_init_script("""Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); window.chrome = { runtime: {} };""")  # self.context.add_init_script(JS)=往每个页面加载前注入一段JS, Object.defineProperty=JS把navigator.webdriver改成undefined(伪装成真人), window.chrome=JS假装有chrome对象(更接近真人浏览器)
        self.page = self.context.new_page()   # self.context.new_page()=在房间里新建一个页面对象(用来操作网页)
        self.context.on("response", self.catch_response)  # self.context.on(事件,回调)=注册监听, response=每次收到响应都触发, catch_response=回调方法(用于抓视频地址)
        self._goto_site()              # self._goto_site()=调用"回首页并关弹窗"的方法
        self.log("✅ 已进入 动漫站 搜索页面")  # self.log()=记录日志
    def _goto_site(self):              # def=定义函数, _goto_site=回网站首页方法(被 on_start/do_back_to_list/do_back_to_search 调用)
        self.page.goto(TARGET_SITE, timeout=0, wait_until="domcontentloaded")  # self.page.goto(网址)=打开网页, timeout=0=不限时等待, wait_until="domcontentloaded"=等网页骨架(DOM)搭好再继续
        time.sleep(2)                  # time.sleep(2)=暂停2秒, 给网页完整渲染时间(要求: 进入层级要给加载时间)
        try:                           # try=尝试
            self.page.locator('//a[**(@class,"**")]').wait_for(state="visible", timeout=8000)  # 等关闭公告按钮出现
            self.page.locator('//a[**(@class,"**")]').click()  # .click()=点击这个关闭公告按钮
            time.sleep(1)              # time.sleep(1)=暂停1秒, 等弹窗关闭动画完成
        except Exception:              # except=找不到关闭按钮就跳过(没有弹窗)
            pass                       # pass=什么都不做
        self.level = "search"          # self.level=记录当前层级为搜索页
    def catch_response(self, r):       # def=定义函数, catch_response=响应回调方法(被 self.context.on("response",...)注册调用), r=响应对象
        if "**" in r.url and self.video_target_url is None:  # r.url=这条响应的网址, in=判断网址里是否含"**"(视频特征), is None=还没存过
            self.video_target_url = r.url  # self.video_target_url=把视频地址存起来
            self.log(f"[抓到视频地址] {self.video_target_url}")  # self.log()=记录日志
    def do_search(self, cmd):          # def=定义函数, do_search=搜索方法(由基类run()按指令名"search"找到并调用), cmd=指令字典
        kw = cmd["kw"]                 # cmd["kw"]=从指令字典里取关键词, kw=关键词变量
        input_box = self.page.locator('//input[contains(@class,"**")]')  # 按XPath定位搜索输入框
        input_box.wait_for(state="visible", timeout=15000)  # input_box.wait_for()=等输入框可见, 15秒
        input_box.fill('')             # input_box.fill('')=把输入框清空(填入空字符串)
        input_box.fill(kw)             # input_box.fill(kw)=把关键词填入输入框
        time.sleep(1)                  # time.sleep(1)=暂停1秒
        self.page.locator('//button[contains(@class,"**")]').click()  # 点击搜索按钮
        time.sleep(2)                  # time.sleep(2)=暂停2秒, 等搜索结果加载出来
        titles = self.page.evaluate("() => Array.from(document.querySelectorAll('h5.card-title a')).map(el => el.innerText)")  # self.page.evaluate(JS)=在网页里执行JS, 一次性取出所有结果标题, titles=标题列表
        if not titles:                 # if not titles=如果列表为空(没搜到)
            self.log("搜索内容为空，请重新输入！")  # 记录日志
            self.res_q.put({"type": "search_result", "titles": []})  # self.res_q.put()=发纸条给窗口(空结果)
            return                     # return=提前结束本方法
        self.result_locators = self.page.locator('//h5[@class="card-title"]/a').all()  # .locator().all()=取所有结果元素句柄列表, 存到self.result_locators(以后点第几个结果用)
        self.log(f"共找到 {len(titles)} 部番剧")  # len()=计算数量
        self.level = "results"         # self.level=记录层级为结果页
        self.res_q.put({"type": "search_result", "titles": titles})  # 把结果标题列表发给窗口
    def do_open_anime(self, cmd):      # def=定义函数, do_open_anime=打开番剧方法(由run()按"open_anime"调用), cmd=指令字典
        idx = cmd["idx"]               # cmd["idx"]=取序号(从0开始), idx=序号变量
        if not (0 <= idx < len(self.result_locators)):  # 判断序号是否越界, len()=结果总数
            self.log("序号超出范围")     # 记录日志
            return                     # return=结束
        self.anime_name = self.result_locators[idx].inner_text(timeout=5000)  # .inner_text()=取该结果元素显示的标题文字(最多等5秒), 存入self.anime_name
        self.result_locators[idx].click()  # .click()=点击这个结果, 浏览器进入详情页
        time.sleep(3)                  # time.sleep(3)=暂停3秒, 给详情页加载时间(要求: 进入层级要给加载时间)
        self.ep_locators = self.page.locator('//div[@id="**"]//ul[contains(@class,"**")]/**').all()  # 取详情页所有集数元素句柄
        self.ep_names = self.page.evaluate("() => Array.from(document.querySelectorAll('#playlist-source .ep-list a')).map(el => el.innerText.trim())")  # 用JS取所有集数名字
        self.log(f"已进入: {self.anime_name}，共 {len(self.ep_names)} 集")  # 记录日志
        self.level = "detail"          # self.level=记录层级为详情页
        self.res_q.put({"type": "episodes", "episodes": self.ep_names, "anime": self.anime_name})  # 把集数表和番名发给窗口, 窗口切换到详情页
    def do_watch(self, cmd):           # def=定义函数, do_watch=在线观看方法(由run()按"watch"调用), cmd=指令字典
        idx = cmd["ep"] - 1            # cmd["ep"]=用户输入的集数(从1开始), -1=减1变成下标(从0开始), idx=下标变量
        if not (0 <= idx < len(self.ep_locators)):  # 判断集数是否越界
            self.log("集数序号超出范围")  # 记录日志
            return                     # return=结束
        self.ep_locators[idx].click()  # .click()=点击这一集, 浏览器进入播放页
        time.sleep(3)                  # time.sleep(3)=暂停3秒, 给播放页加载时间(要求: 进入层级要给加载时间)
        self.log(f"▶ 正在在线观看: {self.anime_name} 第{cmd['ep']}集")  # 记录日志
        self.log(f"当前播放页: {self.page.url}")  # self.page.url=当前页面网址
        self.video_target_url = None   # 清空视频地址盒子, 准备装新的
        retry = 0                      # retry=重试计数器, 从0开始
        while self.video_target_url is None and retry < MAX_RETRY:  # while=循环, 条件是"还没抓到视频地址"且"没超过最大重试次数"
            self.log(f"第 {retry + 1} 次等待视频加载...")  # 记录日志
            time.sleep(WAIT_SEC)       # time.sleep(WAIT_SEC)=等20秒, 让播放器请求视频地址
            if self.video_target_url is None:  # 如果还没抓到
                self.log("未获取到链接，刷新页面重试")  # 记录日志
                self.page.reload(wait_until="domcontentloaded")  # self.page.reload()=刷新页面, 触发播放器重新请求视频
                retry += 1             # retry += 1=重试次数加1
        if self.video_target_url:      # if=如果抓到了视频地址
            self.log(f"本集视频链接: {self.video_target_url}")  # 记录日志
        else:                          # else=没抓到
            self.log("多次重试后仍未获取到视频链接")  # 记录日志
        self.level = "player"          # self.level=记录层级为播放页
        self.res_q.put({"type": "watching"})  # 发纸条给窗口: 正在播放
    def do_download_one(self, cmd):    # def=定义函数, do_download_one=单集下载方法(由run()按"download_one"调用), cmd=指令字典
        idx = cmd["ep"] - 1            # cmd["ep"]-1=把用户输入的集数转成下标
        if not (0 <= idx < len(self.ep_locators)):  # 判断越界
            self.log("集数序号超出范围")  # 记录日志
            return                     # return=结束
        self.ep_locators[idx].click()  # .click()=点击这一集进播放页
        time.sleep(3)                  # time.sleep(3)=给播放页加载时间
        self.video_target_url = None   # 清空视频地址
        retry = 0                      # retry=重试计数器
        while self.video_target_url is None and retry < MAX_RETRY:  # while=循环等视频地址
            time.sleep(WAIT_SEC)       # 等20秒
            if self.video_target_url is None:  # 没抓到就刷新
                self.page.reload(wait_until="domcontentloaded")  # self.page.reload()=刷新页面
                retry += 1             # 重试次数加1
        if self.video_target_url:      # 如果抓到了视频地址
            file_name = f"{self.anime_name}_{self.ep_names[idx]}.mp4"  # f字符串拼接文件名, 如"某动漫_第01集.mp4"
            self.log(f"开始下载: {file_name}")  # 记录日志
            if self._download_file(file_name, self.video_target_url):  # self._download_file()=调用下载方法, 返回True=成功
                self.log(f"下载完成: {file_name}")  # 记录日志
            else:                      # else=下载失败
                self.log("下载失败")    # 记录日志
        else:                          # else=没抓到地址
            self.log("未获取到视频链接，下载失败")  # 记录日志
        self.video_target_url = None   # 用完清空
        time.sleep(2)                  # time.sleep(2)=暂停2秒, 等下载收尾
        self._goto_site()              # 下载完自动回搜索页
        self.log("已回到搜索页面")       # 记录日志
        self.res_q.put({"type": "nav", "to": "search"})  # 发纸条给窗口: 切回搜索页
    def do_download_all(self, cmd):    # def=定义函数, do_download_all=全部下载方法(由run()按"download_all"调用), cmd=指令字典
        total = len(self.ep_names)     # len()=统计一共多少集, total=总集数变量
        self.log(f"===== 开始批量下载 共{total}集 =====")  # 记录日志
        for idx_all in range(total):   # for=循环, range(total)=生成0到total-1的序列, idx_all=当前第几集的下标
            self.log(f"--- 第 {idx_all + 1} 集 / 共{total}集 ---")  # 记录日志
            self.ep_locators[idx_all].click()  # click()=点击这一集进播放页
            time.sleep(3)              # time.sleep(3)=给播放页加载时间
            self.video_target_url = None  # 清空视频地址
            retry = 0                  # retry=重试计数器
            while self.video_target_url is None and retry < MAX_RETRY:  # while=循环等视频地址
                time.sleep(WAIT_SEC)   # 等20秒
                if self.video_target_url is None:  # 没抓到就刷新
                    self.page.reload(wait_until="domcontentloaded")  # 刷新页面
                    retry += 1         # 重试次数加1
            if self.video_target_url:  # 抓到了就下载
                file_name = f"{self.anime_name}_{self.ep_names[idx_all]}.mp4"  # 拼文件名
                self.log(f"开始下载: {file_name}")  # 记录日志
                if self._download_file(file_name, self.video_target_url):  # 调用下载方法
                    self.log(f"第 {idx_all + 1} 集下载完成")  # 记录日志
                else:                  # else=下载失败
                    self.log(f"第 {idx_all + 1} 集下载失败,跳过")  # 记录日志并跳过
            else:                      # else=没抓到地址
                self.log(f"第 {idx_all + 1} 集获取链接失败,跳过")  # 记录日志并跳过
            self.video_target_url = None  # 用完清空
            try:                       # try=尝试
                self.page.go_back(wait_until="domcontentloaded", timeout=30000)  # self.page.go_back()=浏览器后退一步, 回详情页准备下下集, timeout=30000=最多等30秒
                time.sleep(2)          # time.sleep(2)=给返回加载时间(要求: 返回层级要给加载时间)
            except Exception:          # except=后退失败
                time.sleep(1)          # time.sleep(1)=等1秒继续
        self.log("全部集数下载完成，返回搜索页面")  # 记录日志
        time.sleep(2)                  # time.sleep(2)=等收尾
        self._goto_site()              # 全部下完回搜索页
        self.res_q.put({"type": "nav", "to": "search"})  # 发纸条给窗口: 切回搜索页
    def _download_file(self, file_name, url):  # def=定义函数, _download_file=下载文件方法, file_name=保存的文件名, url=视频地址
        MAX_DOWNLOAD_RETRY = 3         # MAX_DOWNLOAD_RETRY=一个文件最多尝试下载3次
        READ_TIMEOUT = 20              # READ_TIMEOUT=连续20秒收不到数据就断开
        safe_name = re.sub(r'[\\/:*?"<>|]', '_', file_name)  # re.sub(规则,替换成,字符串)=把文件名里的非法字符(\/:*?"<>|)替换成_, 防止保存失败
        for retry_cnt in range(MAX_DOWNLOAD_RETRY):  # for=循环尝试下载, retry_cnt=第几次
            try:                       # try=尝试
                resp = requests.get(url=url, headers=HEADERS, stream=True, timeout=(30, READ_TIMEOUT))  # requests.get()=请求视频, headers=伪装头, stream=True=边下边存(流式), timeout=(连接超时,读取超时)
                resp.raise_for_status()  # resp.raise_for_status()=如果网站返回错误状态码就抛异常
                total = int(resp.headers.get("Content-Length") or 0)  # resp.headers=响应头字典, Content-Length=服务器告知的文件总大小(字节), or 0=没告知就按0(未知大小)
                downloaded = 0         # downloaded=已下载字节数计数器, 从0开始
                last_send = 0.0        # last_send=上次发进度纸条的时间戳(用来限流, 防止把结果信箱塞爆)
                with open(safe_name, 'wb') as f:  # open(文件名,'wb')=打开文件准备写入, wb=二进制写入模式, with=自动关闭文件, f=文件对象
                    for chunk in resp.iter_content(chunk_size=1024 * 1024):  # resp.iter_content()=一块一块读取数据, chunk_size=每块1MB, chunk=当前块数据
                        if chunk:      # if chunk=如果这块数据不为空
                            f.write(chunk)  # f.write()=把这块数据写入文件
                            downloaded += len(chunk)  # downloaded += len(chunk)=累加这块数据的字节数(len()=算这块有多少字节)
                            now = time.time()  # now=time.time()=取当前时间戳(秒)
                            if now - last_send >= 0.2:  # if=距上次发进度超过0.2秒才发(限流: 不用每1MB都发, 防止信箱堆积)
                                last_send = now  # 记录本次发送时间
                                self._send_progress(safe_name, downloaded, total)  # self._send_progress()=发一条"下载进度"纸条给窗口
                if total > 0 and downloaded < total:  # if=服务器告知了总大小但实际没下够=下载不完整
                    raise RuntimeError(f"下载不完整: 已下{downloaded}字节/共{total}字节, 连接提前中断")  # raise=主动抛异常, 走下面except重试逻辑(会删掉半截文件重来)
                self._send_progress(safe_name, downloaded, total, done=True)  # 循环正常结束且数据完整=下载完成, 强制发一条100%收尾纸条
                return True            # return True=下载成功
            except Exception as e:     # except=捕获下载异常
                self.log(f"第{retry_cnt + 1}/{MAX_DOWNLOAD_RETRY}次下载失败: {str(e)}")  # 记录日志
                if os.path.exists(safe_name):  # os.path.exists(路径)=判断文件是否存在
                    try:               # try=尝试
                        os.remove(safe_name)  # os.remove(路径)=删除这个不完整的文件
                    except Exception:  # except=删不掉就算了
                        pass           # pass=什么都不做
                self._send_progress(safe_name, 0, 0, failed=True)  # 发"下载出错"纸条, 窗口收到会把进度条清零并提示准备重试
                time.sleep(3)          # time.sleep(3)=等3秒再重试
        return False                   # return False=几次都失败
    def _send_progress(self, file_name, downloaded, total, done=False, failed=False):  # def=定义函数, _send_progress=发进度方法, file_name=文件名, downloaded=已下载字节, total=总字节, done=True=下完的收尾纸条, failed=True=出错的清零纸条
        self.res_q.put({               # self.res_q.put()=往结果信箱塞纸条(窗口每0.1秒轮询取走显示)
            "type": "progress",        # type="progress"=纸条类型是"下载进度", 窗口_handle按这个分发
            "file": file_name,         # file=正在下载的文件名(窗口显示用)
            "done": downloaded,        # done=已下载字节数
            "total": total,            # total=文件总字节数(0=服务器没告知总大小)
            "finished": done,          # finished=True=这是"下完了"的收尾纸条
            "failed": failed,          # failed=True=这是"出错了"的清零纸条
        })                             # 纸条塞完
    def do_back_to_list(self, cmd):    # def=定义函数, do_back_to_list=返回上层方法(由run()按"back_to_list"调用), cmd=指令字典
        if self.level == "player":     # if=如果当前在播放页
            self.page.go_back(wait_until="domcontentloaded", timeout=30000)  # self.page.go_back()=浏览器后退一步, 回详情页
            time.sleep(2)              # time.sleep(2)=给返回加载时间(要求: 返回层级要给加载时间)
            self.level = "detail"      # self.level=更新层级为详情页
            self.log("已返回番剧详情页")  # 记录日志
            self.res_q.put({"type": "nav", "to": "detail"})  # 发纸条给窗口: 切到详情页
        elif self.level == "detail":   # elif=否则如果当前在详情页
            self.page.go_back(wait_until="domcontentloaded", timeout=30000)  # 后退回搜索结果页
            time.sleep(2)              # 给返回加载时间
            self.level = "results"     # 更新层级为结果页
            self.log("已返回搜索结果页")  # 记录日志
            self.res_q.put({"type": "nav", "to": "results"})  # 发纸条给窗口: 切到结果页
        elif self.level == "results":  # elif=否则如果当前在结果页
            self._goto_site()          # 直接回首页搜索页
            self.log("已回到搜索页面")   # 记录日志
            self.res_q.put({"type": "nav", "to": "search"})  # 发纸条给窗口: 切到搜索页
    def do_back_to_search(self, cmd):  # def=定义函数, do_back_to_search=回搜索页方法(由run()按"back_to_search"调用), cmd=指令字典
        self._goto_site()              # 回首页
        self.log("已回到搜索页面")       # 记录日志
        self.res_q.put({"type": "nav", "to": "search"})  # 发纸条给窗口: 切到搜索页
    def do_exit(self, cmd):            # def=定义函数, do_exit=退出方法(由run()按"exit"调用), cmd=指令字典
        self.running = False           # self.running=False=关掉上班开关, while循环停止, 之后执行on_exit关闭浏览器
class App(tk.Tk):
    def __init__(self):                # def=定义函数, __init__=构造函数(创建App()时自动调用)
        super().__init__()             # super()=父类(tk.Tk)引用, .__init__()=先把主窗口造出来
        self.title("全自动视频爬取 窗口版")  # self.title(文字)=设置窗口标题栏文字
        self.geometry("920x680")       # self.geometry(尺寸)=设置窗口大小(宽x高)
        self.minsize(760, 560)         # self.minsize(宽,高)=设置窗口最小尺寸
        self.cmd_q = queue.Queue()     # self.cmd_q=创建"窗口→浏览器"指令信箱
        self.res_q = queue.Queue()     # self.res_q=创建"浏览器→窗口"结果信箱
        self.worker = None             # self.worker=机器人对象(先空着, 进入项目才创建)
        self.current_project = None    # self.current_project=当前进入的项目字典
        self.titles = []               # self.titles=存搜索结果标题列表
        self.ep_names = []             # self.ep_names=存集数列表
        self.anime_name = ""           # self.anime_name=存番剧名
        self.protocol("WM_DELETE_WINDOW", self._on_close)  # self.protocol(事件,回调)=绑定窗口右上角X按钮, 点了就调用self._on_close
        self._build_home()             # 调用"画首页"方法
        self.after(100, self._poll_results)  # self.after(毫秒,函数)=0.1秒后自动调用一次_poll_results(定时检查结果信箱)
    def _build_home(self):             # def=定义函数, _build_home=画首页方法
        self.home_frame = tk.Frame(self, bg="#f0f2f5")  # tk.Frame(父窗口)=创建容器, bg="#f0f2f5"=背景颜色, self.home_frame=首页容器
        self.home_frame.pack(fill="both", expand=True)  # .pack()=把容器放进窗口, fill="both"=填满, expand=True=可扩展
        tk.Label(self.home_frame, text="全自动视频爬取 · 项目选择", font=("Microsoft YaHei", 18, "bold"), bg="#f0f2f5", fg="#1f2937").pack(pady=(40, 5))  # tk.Label()=创建文字标签, text=文字内容, font=字体(微软雅黑,字号,加粗), fg=文字颜色, .pack()=摆放, pady=上下间距
        tk.Label(self.home_frame, text="点击按钮进入对应网站", font=("Microsoft YaHei", 10), bg="#f0f2f5", fg="#6b7280").pack()  # 提示文字标签
        card = tk.Frame(self.home_frame, bg="#ffffff")  # card=放按钮的白色卡片容器
        card.pack(pady=30)             # 摆放卡片
        for p in PROJECTS:             # for=循环遍历项目登记表, p=当前项目字典
            if p["ready"]:             # if=如果这个项目可用
                btn = tk.Button(card, text=f"▶ {p['name']}\n{p['site']}", width=24, height=3, font=("Microsoft YaHei", 12, "bold"), bg="#2563eb", fg="white", activebackground="#1d4ed8", cursor="hand2", command=lambda proj=p: self._enter_project(proj))  # tk.Button()=创建按钮, text=按钮文字, width/height=尺寸, bg=按钮颜色, command=点击时执行的函数(lambda=临时小函数, proj=p=锁定当前项目)
            else:                      # else=项目未完成
                btn = tk.Button(card, text=f"{p['name']}\n(未完成, 后续加入)", width=24, height=3, font=("Microsoft YaHei", 12), bg="#d1d5db", fg="#6b7280", state="disabled")  # state="disabled"=灰色不可点击
            btn.pack(side="left", padx=12)  # btn.pack()=摆放按钮, side="left"=从左往右排列, padx=左右间距
        tk.Label(self.home_frame, text="进入 动漫站 后: 输入搜索 → 点结果 → 在线观看/下载 → 可随时按钮返回上层/搜索页/首页", font=("Microsoft YaHei", 9), bg="#f0f2f5", fg="#9ca3af").pack(side="bottom", pady=12)  # 底部提示文字
    def _enter_project(self, proj):    # def=定义函数, _enter_project=进入项目方法, proj=被点击的项目字典
        self.current_project = proj    # self.current_project=记住当前项目
        self.home_frame.pack_forget()  # self.home_frame.pack_forget()=把首页容器隐藏起来(不显示)
        if self.worker is None:        # if=如果机器人还没创建过
            self.worker = AnimeWorker(self.cmd_q, self.res_q)  # AnimeWorker(指令信箱,结果信箱)=创建机器人对象
            self.worker.start()        # self.worker.start()=启动机器人线程(开始开浏览器进网站)
        self._build_project_frame()    # 调用"画项目界面"方法
    def _build_project_frame(self):    # def=定义函数, _build_project_frame=画项目界面方法
        pf = tk.Frame(self, bg="#f0f2f5")  # pf=项目界面容器
        self.project_frame = pf        # self.project_frame=记住这个容器(以后返回首页要隐藏它)
        pf.pack(fill="both", expand=True)  # 铺满窗口
        top = tk.Frame(pf, bg="#1f2937")   # top=顶部深色栏容器
        top.pack(fill="x")             # fill="x"=横向铺满
        tk.Label(top, text="动漫站", font=("Microsoft YaHei", 14, "bold"), bg="#1f2937", fg="white").pack(side="left", padx=15, pady=8)  # 顶栏左边显示项目名
        self.btn_top = tk.Button(top, text="← 返回上层", command=self._back_upper, bg="#374151", fg="white", relief="flat", cursor="hand2")  # self.btn_top=返回上层按钮, command=点击调用_back_upper
        self.btn_top.pack(side="left", padx=5, pady=8)  # 摆放按钮
        self.btn_search = tk.Button(top, text="回到搜索页面", command=self._back_search, bg="#374151", fg="white", relief="flat", cursor="hand2")  # self.btn_search=回搜索页按钮, command=点击调用_back_search
        self.btn_search.pack(side="left", padx=5, pady=8)  # 摆放按钮
        tk.Button(top, text="🏠 返回首页", command=self._back_home, bg="#374151", fg="white", relief="flat", cursor="hand2").pack(side="right", padx=10, pady=8)  # 返回首页按钮(右边), command=点击调用_back_home
        self.content = tk.Frame(pf, bg="#f0f2f5")  # self.content=中间内容区容器(切换显示搜索/结果/详情页)
        self.content.pack(fill="both", expand=True, padx=10, pady=10)  # 铺满中间区域
        prog = tk.LabelFrame(pf, text=" 下载进度 ", font=("Microsoft YaHei", 10, "bold"))  # prog=带标题的下载进度容器(LabelFrame=带边框文字的容器)
        prog.pack(fill="x", padx=10, pady=(0, 10))  # 横向铺满, 摆在日志框上方
        self.progress_label = tk.Label(prog, text="暂无下载任务", font=("Microsoft YaHei", 9), bg="#f0f2f5", fg="#374151", anchor="w")  # self.progress_label=进度文字标签(显示 文件名/已下载/总大小/百分比), anchor="w"=文字靠左对齐
        self.progress_label.pack(fill="x", padx=5)  # 摆放进度文字
        self.progress_bar = ttk.Progressbar(prog, maximum=100, value=0)  # self.progress_bar=进度条控件, maximum=100=满格是100, value=0=当前0%
        self.progress_bar.pack(fill="x", padx=5, pady=(0, 5))  # 横向铺满进度条
        logbox = tk.LabelFrame(pf, text=" 运行日志 / 打印结果 ", font=("Microsoft YaHei", 10, "bold"))  # logbox=带标题的日志容器, LabelFrame=带边框文字的容器
        logbox.pack(fill="x", padx=10, pady=(0, 10))  # 横向铺满
        self.log_text = scrolledtext.ScrolledText(logbox, height=10, state="disabled", font=("Consolas", 9))  # self.log_text=滚动文本框, state="disabled"=初始只读, height=10=行高
        self.log_text.pack(fill="both", expand=True, padx=5, pady=5)  # 铺满日志区
        self.page_name = "search"      # self.page_name=记录窗口当前显示哪一页
        self._show_page("search")      # 先显示搜索页
    def _show_page(self, page):        # def=定义函数, _show_page=切页方法, page=要显示的页面名
        for w in self.content.winfo_children():  # self.content.winfo_children()=取内容区里所有子控件, w=当前子控件
            w.destroy()                # w.destroy()=销毁(删除)旧页面控件, 实现换页
        self.page_name = page          # 记录当前页名
        if page == "search":           # if=如果是搜索页
            self._page_search()        # 调用画搜索页方法
        elif page == "results":        # elif=如果是结果页
            self._page_results()       # 调用画结果页方法
        elif page == "detail":         # elif=如果是详情页
            self._page_detail()        # 调用画详情页方法
        self._update_nav()             # 调用刷新顶部导航按钮方法
    def _update_nav(self):             # def=定义函数, _update_nav=刷新导航按钮方法
        enable = self.page_name in ("results", "detail")  # enable=布尔值, 结果页/详情页才需要"返回"按钮
        self.btn_top.config(state="normal" if enable else "disabled")  # .config(state=...)=设置按钮状态, normal=可点, disabled=灰掉
        self.btn_search.config(state="normal" if enable else "disabled")  # 回搜索页按钮同理
    def _page_search(self):            # def=定义函数, _page_search=画搜索页方法
        box = tk.Frame(self.content, bg="#ffffff")  # box=白色内容卡片
        box.pack(pady=40)              # 摆放并留上下间距
        tk.Label(box, text="🔍 视频搜索", font=("Microsoft YaHei", 16, "bold"), bg="#ffffff").pack(pady=10)  # 大标题
        row = tk.Frame(box, bg="#ffffff")  # row=放输入框和按钮的一行容器
        row.pack(pady=10)              # 摆放
        self.entry_kw = tk.Entry(row, width=38, font=("Microsoft YaHei", 12))  # self.entry_kw=搜索关键词输入框, Entry=单行输入框
        self.entry_kw.pack(side="left", padx=5)  # 摆放
        self.entry_kw.bind("<Return>", lambda e: self._do_search())  # .bind(事件,函数)=绑定按键事件, "<Return>"=回车键, 按回车=调用_do_search
        tk.Button(row, text="搜 索", width=10, command=self._do_search, bg="#2563eb", fg="white", font=("Microsoft YaHei", 12), relief="flat", cursor="hand2").pack(side="left", padx=5)  # 搜索按钮, command=点击调用_do_search
        tk.Label(box, text="输入动漫名称后点击【搜索】，浏览器会同步进入该网站并搜索", font=("Microsoft YaHei", 9), bg="#ffffff", fg="#6b7280").pack(pady=5)  # 提示文字
    def _do_search(self):              # def=定义函数, _do_search=执行搜索方法
        kw = self.entry_kw.get().strip()  # self.entry_kw.get()=取输入框文字, .strip()=去掉首尾空格, kw=关键词
        if not kw:                     # if not kw=如果没输入内容
            messagebox.showinfo("提示", "请输入搜索内容")  # messagebox.showinfo(标题,内容)=弹出提示框
            return                     # return=结束
        self._append_log(f"👉 搜索: {kw}")  # self._append_log()=往日志框写一行
        self.worker.submit("search", kw=kw)  # self.worker.submit(指令,数据)=给机器人塞纸条"去搜索"
    def _page_results(self):           # def=定义函数, _page_results=画结果页方法
        tk.Label(self.content, text=f"共找到 {len(self.titles)} 部，点击某部进入 在线观看/下载 页面", font=("Microsoft YaHei", 12, "bold"), bg="#f0f2f5").pack(anchor="w", pady=5)  # 顶部说明文字
        canvas = tk.Canvas(self.content, bg="#f0f2f5", highlightthickness=0)  # canvas=画布(用来做可滚动区域), highlightthickness=0=去边框
        sb = ttk.Scrollbar(self.content, orient="vertical", command=canvas.yview)  # sb=竖直滚动条, command=canvas.yview=控制画布上下滚动
        inner = tk.Frame(canvas, bg="#f0f2f5")  # inner=画布里的实际内容容器
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))  # .bind("<Configure>")=内容变化时刷新滚动范围, canvas.bbox("all")=算出内容整体范围
        canvas.create_window((0, 0), window=inner, anchor="nw")  # canvas.create_window()=把inner放到画布左上角, anchor="nw"=左上对齐
        canvas.configure(yscrollcommand=sb.set)  # 让滚动条跟着画布位置走
        canvas.pack(side="left", fill="both", expand=True)  # 画布占左, 铺满
        sb.pack(side="right", fill="y")  # 滚动条占右, 纵向铺满
        for i, t in enumerate(self.titles, 1):  # for=遍历结果, enumerate(列表,起始值)=同时取序号和内容, i=第几个(从1), t=标题
            tk.Button(inner, text=f"第{i}部 | {t}", font=("Microsoft YaHei", 11), anchor="w", relief="solid", bd=1, cursor="hand2", command=lambda idx=i - 1: self._open_anime(idx)).pack(fill="x", padx=6, pady=3)
    def _open_anime(self, idx):        # def=定义函数, _open_anime=打开番剧方法, idx=结果下标
        self._append_log(f"👉 点击进入 第{idx + 1}部, 浏览器同步进入该番剧...")  # 写日志
        self.worker.submit("open_anime", idx=idx)  # 给机器人塞纸条"打开第几个结果"
    def _page_detail(self):            # def=定义函数, _page_detail=画详情页方法
        tk.Label(self.content, text=f"📺 {self.anime_name}   (共 {len(self.ep_names)} 集)", font=("Microsoft YaHei", 13, "bold"), bg="#f0f2f5").pack(anchor="w", pady=5)  # 显示番名和集数
        mid = tk.Frame(self.content, bg="#f0f2f5")  # mid=中间左右分栏容器
        mid.pack(fill="both", expand=True)  # 铺满
        left = tk.Frame(mid, bg="#ffffff")  # left=左边集数列表容器
        left.pack(side="left", fill="both", expand=True, padx=(0, 8))  # 占左
        lb = tk.Listbox(left, font=("Microsoft YaHei", 10), activestyle="none")  # lb=只读集数列表, Listbox=列表控件, activestyle="none"=选中不高亮
        for i, ep in enumerate(self.ep_names, 1):  # 遍历集数
            lb.insert(tk.END, f"{i}. {ep}")  # lb.insert(位置,文字)=往列表末尾加一行
        sbl = ttk.Scrollbar(left, command=lb.yview)  # 列表的滚动条
        lb.configure(yscrollcommand=sbl.set)  # 联动
        lb.pack(side="left", fill="both", expand=True)  # 列表占左
        sbl.pack(side="right", fill="y")  # 滚动条占右
        right = tk.Frame(mid, bg="#ffffff", padx=15, pady=15)  # right=右边操作区容器
        right.pack(side="left", fill="y")  # 占右
        tk.Label(right, text="选择集数(输入数字):", bg="#ffffff", font=("Microsoft YaHei", 10)).pack(anchor="w")  # 提示文字
        self.entry_ep = tk.Entry(right, width=12, font=("Microsoft YaHei", 12))  # self.entry_ep=集数输入框
        self.entry_ep.pack(anchor="w", pady=4)  # 摆放
        self.watch_mode = tk.BooleanVar(value=True)  # self.watch_mode=单选变量(记着选"看"还是"下"), BooleanVar=布尔变量, value=True=默认在线观看
        tk.Radiobutton(right, text="在线观看(浏览器播放)", variable=self.watch_mode, value=True, bg="#ffffff", font=("Microsoft YaHei", 10)).pack(anchor="w")  # Radiobutton=单选按钮, variable=关联的变量, value=True=选这个时变量=True
        tk.Radiobutton(right, text="单集下载(保存MP4)", variable=self.watch_mode, value=False, bg="#ffffff", font=("Microsoft YaHei", 10)).pack(anchor="w")  # value=False=选这个时变量=False
        tk.Button(right, text="✔ 确定执行", command=self._do_ep_action, bg="#16a34a", fg="white", font=("Microsoft YaHei", 11), relief="flat", cursor="hand2").pack(fill="x", pady=6)  # 确定执行按钮, command=调用_do_ep_action
        tk.Button(right, text="⬇ 全部下载", command=lambda: self.worker.submit("download_all"), bg="#ea580c", fg="white", font=("Microsoft YaHei", 11), relief="flat", cursor="hand2").pack(fill="x", pady=6)  # 全部下载按钮, command=直接给机器人发download_all指令
        tk.Button(right, text="↩ 返回选番列表", command=lambda: self.worker.submit("back_to_list"), bg="#475569", fg="white", font=("Microsoft YaHei", 11), relief="flat", cursor="hand2").pack(fill="x", pady=6)  # 返回上层按钮, command=发back_to_list指令
        tk.Button(right, text="↩ 回到搜索页面", command=self._back_search, bg="#475569", fg="white", font=("Microsoft YaHei", 11), relief="flat", cursor="hand2").pack(fill="x", pady=6)  # 回搜索页按钮
    def _do_ep_action(self):           # def=定义函数, _do_ep_action=执行集数操作的方法
        s = self.entry_ep.get().strip()  # 取输入的集数文字
        try:                           # try=尝试
            n = int(s)                 # int(文字)=把字符串转成整数, n=集数
        except ValueError:             # except=捕获转换失败
            messagebox.showinfo("提示", "请输入集数序号(数字)")  # 弹提示框
            return                     # return=结束
        if self.watch_mode.get():      # self.watch_mode.get()=取单选变量的值, True=在线观看
            self.worker.submit("watch", ep=n)  # 发watch指令
            self._append_log(f"▶ 正在打开 第{n}集 在线观看...")  # 写日志
        else:                          # else=下载
            self.worker.submit("download_one", ep=n)  # 发download_one指令
            self._append_log(f"⬇ 开始下载 第{n}集 ...")  # 写日志
    def _back_upper(self):             # def=定义函数, _back_upper=返回上层方法
        if self.page_name in ("results", "detail"):  # 只有在结果页/详情页才需要返回
            self.worker.submit("back_to_list")  # 发back_to_list指令给机器人, 由它按层级决定后退到哪
    def _back_search(self):            # def=定义函数, _back_search=回搜索页方法
        if self.worker:                # if=机器人存在
            self.worker.submit("back_to_search")  # 发back_to_search指令
    def _back_home(self):              # def=定义函数, _back_home=返回首页方法
        if self.worker:                # if=机器人存在
            self.worker.submit("back_to_search")  # 先让浏览器回搜索页, 保证下次进来两边同步
        self.project_frame.pack_forget()  # 隐藏项目界面
        self.home_frame.pack(fill="both", expand=True)  # 重新显示首页
    def _append_log(self, msg):        # def=定义函数, _append_log=写日志方法, msg=日志文字
        self.log_text.configure(state="normal")  # .configure(state="normal")=临时把文本框改成可写
        self.log_text.insert(tk.END, msg + "\n")  # .insert(位置,内容)=在末尾插入一行, "\n"=换行
        self.log_text.see(tk.END)      # .see(位置)=让视图滚到末尾(自动滚到底部)
        self.log_text.configure(state="disabled")  # 再改回只读
    def _poll_results(self):           # def=定义函数, _poll_results=轮询结果信箱方法
        try:                           # try=尝试
            while True:                # while=循环取完所有纸条
                msg = self.res_q.get_nowait()  # self.res_q.get_nowait()=从结果信箱取一条, 没有就抛queue.Empty异常
                self._handle(msg)      # 调用处理纸条的方法
        except queue.Empty:            # except=信箱空了
            pass                       # pass=本次看完
        self.after(100, self._poll_results)  # 再注册0.1秒后再执行一次自己(形成定时轮询)-
    def _handle(self, msg):            # def=定义函数, _handle=处理结果纸条方法, msg=纸条字典
        t = msg.get("type")            # msg.get("type")=取纸条的类型, t=类型
        if t == "log":                 # 如果是日志
            self._append_log(msg["msg"])  # 直接显示
        elif t == "search_result":     # 如果是搜索结果
            self.titles = msg["titles"]  # 存结果标题
            if not self.titles:        # 如果没有结果
                self._append_log("搜索内容为空，请重新输入！")  # 写日志
                self._show_page("search")  # 留在搜索页
                return                 # return=结束
            self._show_page("results")  # 切到结果页
            for i, tt in enumerate(self.titles, 1):  # 遍历结果写日志
                self._append_log(f"第{i}部 - {tt}")  # 写日志
        elif t == "episodes":          # 如果是集数表
            self.anime_name = msg["anime"]  # 存番名
            self.ep_names = msg["episodes"]  # 存集数
            self._show_page("detail")  # 切到详情页
        elif t == "watching":          # 如果是正在播放
            self._append_log("▶ 视频正在浏览器中播放，可在浏览器窗口观看；完成后点击顶部【返回上层】或【回到搜索页面】。")  # 写日志
        elif t == "progress":          # 如果是下载进度纸条
            self._update_progress(msg)  # 调用更新进度条方法(刷新窗口上的进度条)
        elif t == "nav":               # 如果是导航纸条
            if msg.get("to") == "search":  # 目标=搜索页
                self._show_page("search")  # 切到搜索页
            elif msg.get("to") == "results":  # 目标=结果页
                self._show_page("results")  # 切到结果页
            elif msg.get("to") == "detail":  # 目标=详情页
                self._show_page("detail")  # 切到详情页
    def _update_progress(self, msg):   # def=定义函数, _update_progress=更新进度方法, msg=进度纸条字典
        done = msg.get("done", 0)      # msg.get("done",0)=已下载字节数(键不存在就按0)
        total = msg.get("total", 0)    # msg.get("total",0)=文件总字节数
        name = msg.get("file", "")     # msg.get("file","")=正在下载的文件名
        mb = done / (1024 * 1024)      # 已下载字节÷(1024×1024)=换算成MB(1MB=1024×1024字节)
        if msg.get("finished"):        # finished=True=下载完成的收尾纸条
            self.progress_bar.config(value=100)  # .config(value=100)=进度条打满100%
            total_mb = total / (1024 * 1024)  # 总字节数也换算成MB
            self.progress_label.config(text=f"✅ 下载完成: {name}  (共 {total_mb:.1f} MB)" if total > 0 else f"✅ 下载完成: {name}  (共 {mb:.1f} MB)")  # 显示完成信息, :.1f=保留1位小数
        elif msg.get("failed"):        # failed=True=本次尝试出错(半截文件已删, 准备重试)
            self.progress_bar.config(value=0)  # 进度条清零
            self.progress_label.config(text=f"⚠ 下载出错, 准备重试: {name}")  # 显示出错提示
        elif total > 0:                # 服务器告知了总大小(能算百分比)
            pct = int(done * 100 / total)  # pct=百分比=已下载÷总数×100
            self.progress_bar.config(value=pct)  # 进度条走到百分比位置
            self.progress_label.config(text=f"⬇ {name}   {mb:.1f} MB / {total / (1024 * 1024):.1f} MB   ({pct}%)")  # 显示 文件名+已下载/总大小+百分比
        else:                          # 服务器没告知总大小(进度未知)
            self.progress_bar.config(value=0)  # 进度条保持0(没法算百分比)
            self.progress_label.config(text=f"⬇ {name}   已下载 {mb:.1f} MB (总大小未知)")  # 只显示已下载量
    def _on_close(self):               # def=定义函数, _on_close=关闭窗口方法
        if self.worker:                # if=机器人存在
            self.worker.submit("exit")  # 发exit指令让机器人下班(关浏览器)
        self.destroy()                 # self.destroy()=销毁窗口(关掉)
def main():                           # def=定义函数, main=主函数
    app = App()                       # app=创建主窗口对象(会执行App.__init__)
    app.mainloop()                    # app.mainloop()=进入tkinter事件循环, 窗口一直显示并等待操作
if __name__ == "__main__":
    main()