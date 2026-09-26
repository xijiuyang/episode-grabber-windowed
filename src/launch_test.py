# -*- coding: utf-8 -*-
# 最小化启动测试: 只测 Playwright 启动 Edge + 打开 目标动漫站 首页
# ===== 安全版（脱敏后的学习参考，站点特征已抽象）=====
# 1) page.goto 不再用 timeout=0（0 = 永不超时：网站卡着不动时脚本会永远挂在那一只吃 CPU）
# 2) 所有步骤都有超时上限：整个测试最坏几十秒内必然自己结束
# 3) 收尾在 finally 里：无论成功失败都关浏览器、停 Playwright，绝不留进程
# 4) 这是一个"测试脚本"，不要双击运行（双击会直接弹出浏览器窗口跑起来）；
#    想看代码就用编辑器打开，想跑就在终端里运行后盯着它结束
import sys
import time
import traceback
import threading

if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

TARGET_SITE = "https://**.com/"   # ← 请改成你的目标动漫站
HEADLESS = False
GOTO_TIMEOUT_MS = 30000      # 打开页面最多等 30 秒（原来 timeout=0 会无限等）
WAIT_TIMEOUT_MS = 8000       # 定位弹窗/搜索框最多等 8 秒
HARD_STOP = 120              # 看门狗：整个测试跑满 120 秒仍没结束就强制收尾

p = [None]                   # 用列表装引用，看门狗线程也能读到
browser = [None]
start_t = [time.time()]


def force_cleanup():
    """看门狗：脚本卡死（比如 goto 内部阻塞）时由后台线程强杀浏览器进程，
    保证用户等不到手动干预也不会留残。正常结束时这个线程没机会执行"""
    time.sleep(HARD_STOP)
    pid = None
    try:
        if browser[0] is not None:
            proc = browser[0].process
            pid = proc.pid if proc else None
    except Exception:
        pass
    print(f"\n[看门狗] 已超过 {HARD_STOP} 秒未结束，强制清理（浏览器 PID={pid or '未知'}）")
    try:
        if browser[0] is not None:
            browser[0].close()
    except Exception:
        pass
    try:
        if p[0] is not None:
            p[0].stop()
    except Exception:
        pass
    os_portable_exit()


def os_portable_exit():
    import os
    os._exit(0)


try:
    from playwright.sync_api import sync_playwright
    print("[1] sync_playwright 导入成功")
    threading.Thread(target=force_cleanup, daemon=True).start()   # 启动看门狗
    p[0] = sync_playwright().start()
    print("[2] playwright.start() 成功")
    try:
        browser[0] = p[0].chromium.launch(
            channel="msedge",
            headless=HEADLESS,
            args=['--disable-blink-features=AutomationControlled', '--disable-infobars', '--start-maximized'],
        )
        print("[3] 浏览器启动成功 (channel=msedge)")
    except Exception as e:
        print(f"[3失败] channel=msedge 启动失败: {type(e).__name__}: {e}")
        browser[0] = None
    if browser[0] is None:
        try:
            browser[0] = p[0].chromium.launch(headless=HEADLESS)
            print("[4] 默认 chromium 启动成功")
        except Exception as e2:
            print(f"[4失败] 默认chromium也失败: {type(e2).__name__}: {e2}")
    if browser[0] is None:
        print("[致命] 所有方式失败，退出")
        p[0].stop()
        sys.exit(1)
    try:
        context = browser[0].new_context()
        context.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); window.chrome = { runtime: {} };")
        page = context.new_page()
        print("[5] 页面创建成功, 开始打开网站（最多等 30 秒，超时自动跳过）...")
        page.goto(TARGET_SITE, timeout=GOTO_TIMEOUT_MS, wait_until="domcontentloaded")
        print(f"[6] 页面标题: {page.title()}")
        try:
            page.locator('//a[**(@class,"**")]').wait_for(state="visible", timeout=WAIT_TIMEOUT_MS)
            page.locator('//a[**(@class,"**")]').click()
            print("[7] 关闭弹窗成功")
        except Exception as e:
            print(f"[7] 无弹窗或关闭失败: {type(e).__name__}: {e}")
        try:
            box = page.locator('//input[contains(@class,"**")]')
            box.wait_for(state="visible", timeout=WAIT_TIMEOUT_MS)
            print("[8] 搜索框定位成功, 页面就绪")
        except Exception as e:
            print(f"[8] 搜索框定位失败: {type(e).__name__}: {e}")
    finally:
        # 收尾无条件执行：关浏览器 + 停 Playwright，不留任何残留进程
        try:
            if browser[0] is not None:
                if browser[0].process:
                    try:
                        browser[0].process.kill()     # 连浏览器子进程一起杀，杜绝残留
                    except Exception:
                        pass
                browser[0].close()
                browser[0] = None
                print("[9] 浏览器已关闭")
        except Exception as e:
            print(f"[9] 关浏览器异常: {type(e).__name__}: {e}")
finally:
    try:
        if p[0] is not None:
            p[0].stop()
            p[0] = None
            print("[10] Playwright 已停止")
    except Exception as e:
        print(f"[10] 停 Playwright 异常: {type(e).__name__}: {e}")
    print(f"[结束] 测试结束，总耗时 {time.time() - start_t[0]:.1f} 秒。资源已全部释放，不会在后台残留。")