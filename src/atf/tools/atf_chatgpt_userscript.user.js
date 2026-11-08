// ==UserScript==
// @name         ATF ChatGPT Web Bridge
// @namespace    http://tampermonkey.net/
// @version      2.1
// @description  Connects ChatGPT Web UI to ATF: Chunked Direct Typing, Zero File-Attachment Bugs, Safe Composer Scoping, Auto Modal Dismissal, and Screen Wake Lock
// @author       ATF Team
// @match        https://chatgpt.com/*
// @match        https://*.chatgpt.com/*
// @match        https://chat.openai.com/*
// @match        https://*.openai.com/*
// @noframes
// @grant        GM_xmlhttpRequest
// @connect      127.0.0.1
// @connect      localhost
// @run-at       document-end
// ==/UserScript==

(function () {
    'use strict';

    // ป้องกันไม่ให้ทำงานใน iframe (เช่น Cloudflare, Captcha, Analytics) โดยเด็ดขาด 100%
    if (window.top !== window.self) {
        return;
    }

    const BRIDGE_HOST = "http://127.0.0.1:8765";
    const POLL_INTERVAL_MS = 1000;
    let isProcessing = false;
    let isPaused = false;
    let currentTaskId = null;

    // --- Screen Wake Lock (ป้องกันเครื่องดับจอ / Screen Saver ขณะรัน) ---
    let screenWakeLock = null;
    async function requestScreenWakeLock() {
        try {
            if ('wakeLock' in navigator && !screenWakeLock) {
                screenWakeLock = await navigator.wakeLock.request('screen');
                screenWakeLock.addEventListener('release', () => {
                    screenWakeLock = null;
                    console.log("[ATF] 🛡️ Screen Wake Lock released.");
                });
                console.log("[ATF] 🛡️ Screen Wake Lock acquired (Screen Saver prevented).");
            }
        } catch (err) {
            console.warn("[ATF] Screen Wake Lock not supported or rejected:", err.message);
        }
    }

    // ขอ Wake Lock ซ้ำเมื่อหน้าเว็บกลับมา Active
    document.addEventListener('visibilitychange', async () => {
        if (document.visibilityState === 'visible') {
            await requestScreenWakeLock();
        }
    });
    // ขอ Wake Lock ทันทีที่โหลดสคริปต์
    requestScreenWakeLock();

    // --- 1. UI Overlay (Status Widget) ---
    const badge = document.createElement("div");
    badge.id = "atf-bridge-widget";
    badge.style.position = "fixed";
    badge.style.bottom = "20px";
    badge.style.right = "20px";
    badge.style.zIndex = "99999";
    badge.style.padding = "10px 16px";
    badge.style.borderRadius = "12px";
    badge.style.backgroundColor = "rgba(24, 24, 27, 0.95)";
    badge.style.border = "1px solid rgba(255, 255, 255, 0.15)";
    badge.style.color = "#fff";
    badge.style.fontFamily = "system-ui, -apple-system, sans-serif";
    badge.style.fontSize = "13px";
    badge.style.boxShadow = "0 8px 32px rgba(0, 0, 0, 0.4)";
    badge.style.display = "flex";
    badge.style.alignItems = "center";
    badge.style.gap = "10px";
    badge.style.transition = "all 0.3s ease";

    badge.innerHTML = `
        <div id="atf-status-dot" style="width: 10px; height: 10px; border-radius: 50%; background-color: #888;"></div>
        <div style="display: flex; flex-direction: column;">
            <span style="font-weight: 600; font-size: 13px;">ATF Bridge v1.6 🛡️⚡</span>
            <span id="atf-status-text" style="font-size: 11px; color: #a1a1aa;">Connecting...</span>
        </div>
        <button id="atf-toggle-btn" style="margin-left: 8px; padding: 4px 8px; border-radius: 6px; border: none; background: rgba(255,255,255,0.1); color: #fff; cursor: pointer; font-size: 11px;">Pause</button>
        <button id="atf-reset-btn" style="margin-left: 4px; padding: 4px 8px; border-radius: 6px; border: none; background: rgba(239,68,68,0.3); color: #fff; cursor: pointer; font-size: 11px;">Reset</button>
    `;

    function ensureBadgeMounted() {
        if (!document.getElementById("atf-bridge-widget")) {
            if (document.body) {
                document.body.appendChild(badge);
            } else {
                window.addEventListener('DOMContentLoaded', () => document.body.appendChild(badge));
            }
        }
    }
    ensureBadgeMounted();

    const statusDot = document.getElementById("atf-status-dot");
    const statusText = document.getElementById("atf-status-text");
    const toggleBtn = document.getElementById("atf-toggle-btn");
    const resetBtn = document.getElementById("atf-reset-btn");

    if (toggleBtn) {
        toggleBtn.addEventListener("click", () => {
            isPaused = !isPaused;
            toggleBtn.textContent = isPaused ? "Resume" : "Pause";
            toggleBtn.style.background = isPaused ? "#ef4444" : "rgba(255,255,255,0.1)";
            updateStatus(isPaused ? "Paused by User" : "Ready", isPaused ? "#f59e0b" : "#22c55e");
        });
    }

    if (resetBtn) {
        resetBtn.addEventListener("click", () => {
            isProcessing = false;
            currentTaskId = null;
            updateStatus("Ready (Manually Reset)", "#22c55e");
            console.log("[ATF] Manually reset bridge state.");
        });
    }

    function updateStatus(text, dotColor = "#888") {
        if (statusText) statusText.textContent = text;
        if (statusDot) statusDot.style.backgroundColor = dotColor;
    }

    // --- 2. HTTP Helper (GM_xmlhttpRequest) ---
    function sendHttpRequest(method, path, data = null) {
        return new Promise((resolve, reject) => {
            GM_xmlhttpRequest({
                method: method,
                url: `${BRIDGE_HOST}${path}`,
                headers: { "Content-Type": "application/json" },
                data: data ? JSON.stringify(data) : null,
                timeout: 15000,
                onload: (response) => {
                    try {
                        const json = JSON.parse(response.responseText);
                        resolve(json);
                    } catch (e) {
                        resolve(response.responseText);
                    }
                },
                onerror: (err) => reject(err),
                ontimeout: () => reject(new Error("Timeout"))
            });
        });
    }

    // --- 4. DOM Automation Helpers ---
    async function waitForPromptInput(timeoutMs = 15000, autoRecover = true) {
        const start = Date.now();
        while (Date.now() - start < timeoutMs) {
            // 1. ค้นหากล่องกรอกข้อความทุกรูปแบบของ ChatGPT
            let el = document.querySelector('#prompt-textarea') ||
                document.querySelector('div#prompt-textarea') ||
                document.querySelector('div[contenteditable="true"]') ||
                document.querySelector('[role="textbox"]') ||
                document.querySelector('[data-testid="textbox"]') ||
                document.querySelector('div.ProseMirror') ||
                document.querySelector('form div[contenteditable="true"]') ||
                document.querySelector('form textarea') ||
                document.querySelector('textarea[data-id="root"]') ||
                document.querySelector('textarea') ||
                document.querySelector('footer [contenteditable="true"]');
            if (el && !el.disabled) return el;

            // 2. ตรวจสอบว่ามี Popup หรือ Modal บังอยู่หรือไม่ ถ้ามีให้กด Dismiss อัตโนมัติ (เช่น แจ้งเตือนปักหมุด, Tip, Feature Update)
            const dialogBtns = document.querySelectorAll('div[role="dialog"] button, [role="alertdialog"] button');
            for (const b of dialogBtns) {
                if (b.getAttribute('data-testid') === 'send-button') continue;
                const bText = (b.innerText || b.getAttribute('aria-label') || "").trim().toLowerCase();
                if (bText === "ตกลง" || bText === "ok" || bText.includes("stay") || bText.includes("close") || bText.includes("dismiss") || bText.includes("not now") || bText.includes("ปิด")) {
                    try { b.click(); } catch (e) { }
                }
            }

            // ตรวจสอบปุ่ม "แชทใหม่" บนแถบแจ้งเตือนโควตา (Quota Banner) โดยตรง
            const quotaNewChatBtn = Array.from(document.querySelectorAll('button')).find(b => {
                const t = (b.innerText || "").trim();
                return t === "แชทใหม่" || t === "New chat" || t === "Start new chat";
            });
            if (autoRecover && quotaNewChatBtn) {
                console.warn("[ATF Bridge] Quota Banner 'แชทใหม่' button detected! Auto-clicking...");
                updateStatus("Quota Banner! Clicking 'แชทใหม่'...", "#f59e0b");
                try { quotaNewChatBtn.click(); } catch (e) { }
                await new Promise(r => setTimeout(r, 1500));
            }

            // 3. ตรวจสอบว่าหน้าเว็บติดขีดจำกัดแชต (Message Limit) จนกล่องข้อความถูกซ่อนหรือไม่
            if (autoRecover && checkChatLimitWarning()) {
                console.warn("[ATF Bridge] Message limit banner detected while waiting for input! Auto-opening New Chat...");
                updateStatus("Limit Detected! Auto-opening New Chat...", "#f59e0b");
                await triggerNewChat();
                const recoveredInput = await waitForPromptInput(10000, false);
                if (recoveredInput) return recoveredInput;
            }

            await new Promise(r => setTimeout(r, 400));
        }
        return null;
    }

    function findPromptInput() {
        return document.querySelector('#prompt-textarea') ||
            document.querySelector('div#prompt-textarea') ||
            document.querySelector('div[contenteditable="true"]') ||
            document.querySelector('[role="textbox"]') ||
            document.querySelector('[data-testid="textbox"]') ||
            document.querySelector('div.ProseMirror') ||
            document.querySelector('form div[contenteditable="true"]') ||
            document.querySelector('form textarea') ||
            document.querySelector('textarea[data-id="root"]') ||
            document.querySelector('textarea') ||
            document.querySelector('footer [contenteditable="true"]');
    }

    function getSendButton() {
        return document.querySelector('button[data-testid="send-button"]') ||
            document.querySelector('button[aria-label="Send prompt"]') ||
            document.querySelector('button[data-testid="fruitjuice-send-button"]') ||
            document.querySelector('form button[type="submit"]');
    }

    function isGenerating() {
        // 1. ตรวจสอบปุ่ม Stop ทุกรูปแบบ
        const stopBtn = document.querySelector('button[data-testid="stop-button"]') ||
            document.querySelector('button[aria-label="Stop generating"]') ||
            document.querySelector('button[aria-label="Stop streaming"]') ||
            document.querySelector('button[aria-label="Stop"]') ||
            document.querySelector('button[aria-label*="Stop" i]') ||
            document.querySelector('button[aria-label*="หยุด" i]') ||
            document.querySelector('button[data-testid*="stop" i]');
        if (stopBtn) return true;

        // 2. ตรวจสอบสถานะ streaming
        const isStreaming = document.querySelector('.result-streaming, [class*="streaming"], [data-state="streaming"]') !== null;
        if (isStreaming) return true;

        return false;
    }

    function getLatestAssistantResponse() {
        // 1. ค้นหาจาก Code block ล่าสุดก่อน (กรณีที่ ChatGPT ส่ง JSON มาใน code block)
        const codeBlocks = Array.from(document.querySelectorAll('pre code, pre'));
        for (let i = codeBlocks.length - 1; i >= 0; i--) {
            const cb = codeBlocks[i];
            if (cb.closest('form') || cb.closest('#prompt-textarea')) continue;
            const t = (cb.innerText || "").trim();
            if (t.length > 30 && (t.startsWith('[') || t.includes('"id"'))) {
                return t;
            }
        }

        // 2. ค้นหาจาก Markdown / Prose elements จากท้ายสุดขึ้นมา
        const markdownElements = Array.from(document.querySelectorAll('.markdown, div[class*="markdown"], div.prose, div[class*="prose"]'));
        for (let i = markdownElements.length - 1; i >= 0; i--) {
            const el = markdownElements[i];
            if (el.closest('form') || el.closest('#prompt-textarea') || el.closest('[data-message-author-role="user"]')) {
                continue;
            }
            const t = (el.innerText || "").trim();
            // ต้องมีความยาวมากกว่า 30 ตัวอักษร และไม่ใช่ Prompt ของระบบ
            if (t.length > 30 && !t.toLowerCase().startsWith("you are an elite")) {
                return t;
            }
        }

        // 3. ค้นหาจาก Candidate Containers (Assistant Turn, Agent Turn, Article)
        const candidateContainers = Array.from(document.querySelectorAll('[data-message-author-role="assistant"], div[class*="agent-turn"], article, div[data-testid^="conversation-turn-"]'));
        for (let i = candidateContainers.length - 1; i >= 0; i--) {
            const container = candidateContainers[i];
            if (container.getAttribute('data-message-author-role') === 'user' ||
                container.querySelector('[data-message-author-role="user"]') ||
                container.closest('form')) {
                continue;
            }

            const innerMarkdown = container.querySelector('.markdown, div[class*="markdown"], div.prose, div[class*="prose"], pre code');
            const targetEl = innerMarkdown || container;
            const t = (targetEl.innerText || "").trim();
            if (t.length > 30 && !t.includes("ChatGPT can make mistakes") && !t.toLowerCase().startsWith("you are an elite")) {
                return t;
            }
        }

        return "";
    }

    // ตรวจจับการแจ้งเตือนว่าถึงขีดจำกัดแชต (Message Limit Banner / Warning / Quota Reset)
    function checkChatLimitWarning() {
        const alerts = document.querySelectorAll('[role="alert"], div[class*="banner"], div[class*="warning"], main footer div[class*="banner"]');
        const limitKeywords = [
            "reached the message limit",
            "reached your limit",
            "start a new chat to continue",
            "you've hit the limit",
            "คุณถึงขีดจำกัดแล้ว",
            "เริ่มการแชทใหม่เพื่อดำเนินการต่อ",
            "เริ่มแชตใหม่เพื่อดำเนินการต่อ",
            "ลองใหม่อีกครั้งหลังจาก",
            "try again after",
            "too many requests",
            "usage cap"
        ];

        for (const el of alerts) {
            const t = (el.innerText || "").toLowerCase();
            if (limitKeywords.some(kw => t.includes(kw)) && !t.includes("แชทต่อด้วยข้อความ") && !t.includes("text only")) {
                return true;
            }
        }

        // ตรวจสอบ banner ใกล้ footer / composer
        const footerAlert = document.querySelector('main footer');
        if (footerAlert) {
            const ft = (footerAlert.innerText || "").toLowerCase();
            if (["คุณถึงขีดจำกัดแล้ว", "reached your limit", "start a new chat to continue", "try again after"].some(kw => ft.includes(kw))) {
                return true;
            }
        }

        return false;
    }

    // ตรวจสอบการติด Rate Limit / Cooldown ระดับบัญชีหรือช่วงเวลา (ที่ต้องพักคอย ไม่ใช่แค่เปิด New Chat)
    function checkAccountRateLimit() {
        // จำกัดขอบเขตเฉพาะกล่องแจ้งเตือนข้อผิดพลาดจริง (Alerts / Modals / Banners ใน main หรือ dialog)
        // ⚠️ ห้ามตรวจ document.body.innerText ทั่วทั้งหน้าจอเด็ดขาด เพื่อป้องกัน False Positive จากแถบประวัติแชต (Sidebar)
        const activeContainers = document.querySelectorAll('main [role="alert"], [role="dialog"], div[data-testid*="modal"], main div[class*="banner"], main div[class*="error"], main div[class*="notice"]');
        const accountLimitKeywords = [
            "try again after",
            "ลองใหม่อีกครั้งหลังจาก",
            "too many requests",
            "you've reached your limit",
            "you have reached your limit",
            "reached your limit",
            "คุณถึงขีดจำกัดแล้ว",
            "reached your free usage limit",
            "reached the free usage limit"
        ];

        for (const el of activeContainers) {
            const t = (el.innerText || "").toLowerCase();
            for (const kw of accountLimitKeywords) {
                if (t.includes(kw)) {
                    return { isRateLimited: true, reason: el.innerText.trim() };
                }
            }
        }

        // ตรวจสอบกรณีปุ่ม Send ถูก Disabled ร่วมกับมีแถบแจ้งเตือนที่ Footer ของ Main
        const sendBtn = getSendButton();
        if (sendBtn && (sendBtn.disabled || sendBtn.getAttribute("aria-disabled") === "true")) {
            const footerAlerts = document.querySelectorAll('main footer [role="alert"], main footer div[class*="banner"]');
            for (const el of footerAlerts) {
                const footerText = (el.innerText || "").toLowerCase();
                for (const kw of accountLimitKeywords) {
                    if (footerText.includes(kw)) {
                        return { isRateLimited: true, reason: "Send button disabled by limit banner: " + el.innerText.trim() };
                    }
                }
            }
        }

        return { isRateLimited: false, reason: "" };
    }

    const checkChatLimitBanner = checkChatLimitWarning;

    // ฟังก์ชันลบไฟล์แนบ (Attachment Chip / pasted.txt) ที่อาจค้างอยู่ในกล่องข้อความ
    function clearAttachmentChips() {
        try {
            // จำกัดการค้นหาเฉพาะภายในกล่อง Composer / Form เท่านั้น ห้ามค้นหาทั้งหน้าจอ (ป้องกันโดน Sidebar 100%)
            const composer = document.querySelector('form') ||
                document.querySelector('#prompt-textarea')?.closest('form') ||
                document.querySelector('main footer');
            if (!composer) return;

            const removeSelectors = [
                'button[aria-label*="Remove" i]',
                'button[aria-label*="ลบ" i]',
                'button[data-testid*="remove" i]',
                'div[data-testid*="attachment"] button',
                'div[class*="attachment"] button',
                '.attachment-chip button'
            ];
            for (const sel of removeSelectors) {
                const btns = composer.querySelectorAll(sel);
                for (const b of btns) {
                    const label = (b.getAttribute('aria-label') || b.textContent || '').toLowerCase();
                    if (label.includes('remove') || label.includes('ลบ') || label.includes('file') || label.includes('ไฟล์')) {
                        console.log("[ATF Bridge] Found and clearing stale file attachment chip:", b);
                        b.click();
                    }
                }
            }
        } catch (e) {
            console.warn("[ATF Bridge] Error clearing attachment chips:", e);
        }
    }

    // ฟังก์ชันสั่งขึ้นแชตใหม่ (New Chat) แบบปลอดภัยไม่รีโหลดหน้า พร้อมตรวจสอบ Readiness
    async function triggerNewChat() {
        updateStatus("Opening New Chat...", "#f59e0b");

        // ตรวจสอบปุ่ม "แชทใหม่" บนแถบแจ้งเตือนโควตา (Quota Banner) โดยตรงก่อน
        const bannerNewChatBtn = Array.from(document.querySelectorAll('button')).find(b => {
            const t = (b.innerText || "").trim();
            return t === "แชทใหม่" || t === "New chat" || t === "Start new chat";
        });
        if (bannerNewChatBtn) {
            console.log("[ATF Bridge] Clicking 'แชทใหม่' button on quota banner directly...");
            try { bannerNewChatBtn.click(); } catch (e) { }
            await new Promise(r => setTimeout(r, 1500));
        }

        const newChatBtn = document.querySelector('button[data-testid="new-chat-button"]') ||
            document.querySelector('a[data-testid="new-chat-button"]') ||
            document.querySelector('button[aria-label*="New chat" i]') ||
            document.querySelector('button[aria-label*="แชทใหม่" i]') ||
            document.querySelector('a[aria-label*="New chat" i]') ||
            document.querySelector('nav a[href="/"]');

        if (newChatBtn) {
            newChatBtn.click();
        } else {
            const headerLogo = document.querySelector('header a') || document.querySelector('nav a[href="/"]');
            if (headerLogo) headerLogo.click();
        }

        // ล้างชิปไฟล์แนบตกค้างเฉพาะใน Composer (ถ้ามี)
        clearAttachmentChips();

        // รอจนกว่ากล่อง Prompt textarea จะโหลดขึ้นมาพร้อมใช้งานจริง (Readiness Check)
        const input = await waitForPromptInput(15000);
        if (!input) {
            throw new Error("Timeout waiting for prompt input box after New Chat.");
        }

        await new Promise(r => setTimeout(r, 400));
        updateStatus("New Chat Ready", "#22c55e");
    }

    // ฟังก์ชันล้างกล่องข้อความให้สะอาดเกลี้ยง 100% (ป้องกันไม่ให้วางข้อความต่อท้าย Token บวมเด็ดขาด)
    function clearPromptInput(inputEl) {
        if (!inputEl) return;
        inputEl.focus();
        try {
            document.execCommand('selectAll', false, null);
            document.execCommand('delete', false, null);
        } catch (e) { }

        if (inputEl.tagName && inputEl.tagName.toLowerCase() === 'textarea') {
            inputEl.value = '';
        } else {
            inputEl.innerHTML = '<p><br class="ProseMirror-trailingBreak"></p>';
        }

        inputEl.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'deleteContentBackward' }));
        inputEl.dispatchEvent(new Event('change', { bubbles: true }));
    }

    async function setPromptAndSend(promptText) {
        // เคลียร์ไฟล์แนบเก่า (ถ้ามีค้างอยู่) เพื่อไม่ให้ขัดขวางการส่ง
        clearAttachmentChips();

        // รอให้กล่อง Prompt textarea โหลดขึ้นมาสูงสุด 15 วินาที
        let inputEl = await waitForPromptInput(15000);
        if (!inputEl) {
            // หากยังไม่พบกล่องข้อความ ให้ลองสั่ง New Chat ฉุกเฉิน 1 ครั้งทันที (เผื่อหน้าเดิมติด Limit หรือ DOM ค้าง)
            console.warn("[ATF Bridge] Prompt textarea missing in current chat. Attempting Emergency New Chat recovery...");
            updateStatus("Input missing! Emergency New Chat...", "#f59e0b");
            await triggerNewChat();
            inputEl = await waitForPromptInput(10000, false);
        }

        if (!inputEl) {
            throw new Error("Could not find prompt textarea in ChatGPT UI (Emergency recovery failed).");
        }

        inputEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
        inputEl.click();
        inputEl.focus();

        await new Promise(r => setTimeout(r, 200));

        // ล้างข้อความเก่าที่อาจตกค้างออกให้หมดจด 100% (ป้องกันการวางข้อความซ้ำสะสม Token บวมเด็ดขาด)
        clearPromptInput(inputEl);
        await new Promise(r => setTimeout(r, 150));

        if (inputEl.tagName.toLowerCase() === 'textarea') {
            inputEl.value = promptText;
            inputEl.dispatchEvent(new Event('input', { bubbles: true }));
            inputEl.dispatchEvent(new Event('change', { bubbles: true }));
        } else {
            // สำหรับ ContentEditable / ProseMirror editor ของ ChatGPT
            // ตรวจสอบให้แน่ใจอีกครั้งว่ากล่องว่างเปล่าจริงๆ ก่อนพิมพ์
            if (inputEl.textContent && inputEl.textContent.trim().length > 0) {
                clearPromptInput(inputEl);
                await new Promise(r => setTimeout(r, 100));
            }

            // 2. ป้อนข้อความด้วย document.execCommand('insertText') แบบแบ่ง Chunk (Chunked Direct Typing)
            // ⚠️ ห้ามใช้ ClipboardEvent('paste') เด็ดขาด เพราะ ChatGPT จะดักจับข้อความยาวและแปลงเป็นไฟล์แนบ .txt ทันที
            let inputAccepted = false;
            try {
                inputEl.focus();
                const CHUNK_SIZE = 2500;
                for (let i = 0; i < promptText.length; i += CHUNK_SIZE) {
                    const chunk = promptText.slice(i, i + CHUNK_SIZE);
                    document.execCommand('insertText', false, chunk);
                }
                if (inputEl.textContent && inputEl.textContent.trim().length > 0) {
                    inputAccepted = true;
                }
            } catch (e) {
                console.warn("[ATF Bridge] execCommand chunked insertText failed:", e);
            }

            // 3. Fallback 1: ใช้ InputEvent ('beforeinput')
            if (!inputAccepted) {
                try {
                    inputEl.focus();
                    const beforeInputEvt = new InputEvent('beforeinput', {
                        bubbles: true,
                        cancelable: true,
                        inputType: 'insertText',
                        data: promptText
                    });
                    inputEl.dispatchEvent(beforeInputEvt);
                    if (inputEl.textContent && inputEl.textContent.trim().length > 0) {
                        inputAccepted = true;
                    }
                } catch (e) {
                    console.warn("[ATF Bridge] beforeinput fallback failed:", e);
                }
            }

            // 4. Fallback 2: สร้าง Element <p> ตรงเข้าสู่ DOM ของ ProseMirror
            if (!inputAccepted) {
                try {
                    inputEl.focus();
                    const p = document.createElement('p');
                    p.textContent = promptText;
                    inputEl.innerHTML = '';
                    inputEl.appendChild(p);
                    inputAccepted = true;
                } catch (e) {
                    console.warn("[ATF Bridge] DOM paragraph fallback failed:", e);
                }
            }

            // 5. แจ้ง Dispatch Event input/change เพื่อกระตุ้น React State Sync
            inputEl.dispatchEvent(new Event('input', { bubbles: true }));
            inputEl.dispatchEvent(new Event('change', { bubbles: true }));

            // 6. ตรวจสอบหากมีปุ่ม "Show in text field" หรือ "แสดงในช่องข้อความ" (เผื่อ ChatGPT ยังพยายามแปลงเป็นชิป)
            await new Promise(r => setTimeout(r, 150));
            const showInTextFieldBtns = Array.from(document.querySelectorAll('button')).filter(b => {
                const t = (b.innerText || b.getAttribute('aria-label') || '').toLowerCase();
                return t.includes('show in text field') || t.includes('แสดงในช่องข้อความ');
            });
            for (const btn of showInTextFieldBtns) {
                console.log("[ATF Bridge] Clicking 'Show in text field' button:", btn);
                try { btn.click(); } catch (e) { }
            }
        }

        // รอให้ React อัปเดตสถานะปุ่ม Send ให้พร้อมกด (สูงสุด 3 วินาที)
        let sendBtn = null;
        for (let i = 0; i < 15; i++) {
            await new Promise(r => setTimeout(r, 200));
            sendBtn = getSendButton();
            if (sendBtn && !sendBtn.disabled && !sendBtn.hasAttribute('disabled')) {
                break;
            }
        }

        // จำลองการหยุดตรวจทานของผู้ใช้ (Human Hesitation: 600 - 1,200ms) ก่อนกดปุ่ม Send
        const humanHesitation = 600 + Math.floor(Math.random() * 600);
        await new Promise(r => setTimeout(r, humanHesitation));

        // ตรวจสอบและกดปุ่ม Send หรือปลด disabled เพื่อสั่งคลิก
        if (sendBtn && !sendBtn.disabled && !sendBtn.hasAttribute('disabled')) {
            sendBtn.click();
        } else {
            if (sendBtn) {
                sendBtn.disabled = false;
                sendBtn.removeAttribute('disabled');
                sendBtn.click();
            }

            // กระตุ้นด้วย KeyboardEvent Enter (แบบมี cancelable: true)
            inputEl.dispatchEvent(new KeyboardEvent('keydown', {
                key: 'Enter',
                code: 'Enter',
                keyCode: 13,
                which: 13,
                bubbles: true,
                cancelable: true
            }));

            // สั่ง form.requestSubmit() หาก element อยู่ในฟอร์ม
            const form = inputEl.closest('form');
            if (form && typeof form.requestSubmit === 'function') {
                try {
                    form.requestSubmit();
                } catch (e) { }
            }
        }
    }

    // --- 4. Main Polling and Task Execution Loop ---
    async function processTask(task) {
        isProcessing = true;
        currentTaskId = task.task_id;

        // จัดการ Action: probe_status (ทดสอบสถานะความพร้อมและ Rate Limit สำหรับ Watchdog Sentinel)
        if (task.action === "probe_status") {
            try {
                const limitInfo = checkAccountRateLimit();
                const inputEl = findPromptInput();
                const canSend = (inputEl !== null) && !limitInfo.isRateLimited;
                console.log(`[ATF Bridge] Probe check: can_send=${canSend}, is_rate_limited=${limitInfo.isRateLimited}`);
                await sendHttpRequest("POST", "/bridge/result", {
                    task_id: task.task_id,
                    status: "done",
                    action: "probe_status",
                    can_send: canSend,
                    is_rate_limited: limitInfo.isRateLimited,
                    reason: limitInfo.reason
                });
            } catch (err) {
                await sendHttpRequest("POST", "/bridge/result", {
                    task_id: task.task_id,
                    status: "error",
                    error: err.message
                });
            } finally {
                isProcessing = false;
                currentTaskId = null;
            }
            return;
        }

        // จัดการ Action: refresh_page (รีเฟรชหน้าเว็บเมื่อติด Cooldown ตามคำสั่ง Sentinel Watchdog)
        if (task.action === "refresh_page") {
            console.log("[ATF Bridge] Refreshing page as requested by Sentinel Watchdog...");
            updateStatus("Refreshing page for cooldown check...", "#f59e0b");
            await sendHttpRequest("POST", "/bridge/result", {
                task_id: task.task_id,
                status: "done",
                action: "refresh_page"
            });
            setTimeout(() => {
                window.location.reload();
            }, 600);
            return;
        }

        // จัดการ Action: new_chat
        if (task.action === "new_chat") {
            try {
                await triggerNewChat();
                await sendHttpRequest("POST", "/bridge/result", {
                    task_id: task.task_id,
                    content: "New chat initialized",
                    status: "done",
                    action: "new_chat"
                });
            } catch (err) {
                await sendHttpRequest("POST", "/bridge/result", {
                    task_id: task.task_id,
                    content: "",
                    status: "error",
                    error: err.message
                });
            } finally {
                isProcessing = false;
                currentTaskId = null;
            }
            return;
        }

        // จัดการ Action: send_prompt (การแปลปกติ)
        await requestScreenWakeLock();
        updateStatus(`Running Task #${task.task_id.slice(0, 6)}...`, "#3b82f6");

        try {
            const initialResponse = getLatestAssistantResponse();
            const getTurnCount = () => document.querySelectorAll('article, div[data-testid^="conversation-turn-"], [data-message-author-role="assistant"]').length;
            const initialTurns = getTurnCount();

            await setPromptAndSend(task.prompt);

            // State-Based Generation Start Detection (Zero-Timeout Principle 100%)
            // ไม่ใช้การจับเวลานับถอยหลังตัดจบเด็ดขาด แต่ตรวจสอบสถานะจริงของ DOM และการตอบสนอง
            updateStatus("Waiting for ChatGPT to start...", "#3b82f6");
            let retryCycle = 0;
            while (true) {
                await new Promise(r => setTimeout(r, 600));
                retryCycle++;

                const currentTurns = getTurnCount();
                const latestText = getLatestAssistantResponse();
                const hasNewResponse = (latestText && latestText.trim().length > 0 && latestText !== initialResponse);

                // หากพบว่าปุ่ม Stop แสดงขึ้นมา, หรือมี Turn ใหม่เกิดขึ้น, หรือมีข้อความคำตอบใหม่โผล่ขึ้นมา -> ถือว่าเริ่มสร้างแล้วทันที!
                if (isGenerating() || currentTurns > initialTurns || hasNewResponse) {
                    break;
                }

                // ตรวจสอบข้อผิดพลาดหรือขีดจำกัดชัดเจนบนหน้าเว็บ
                if (checkChatLimitBanner()) {
                    throw new Error("ChatGPT Message Limit Reached (Banner detected).");
                }

                const alertEl = document.querySelector('[role="alert"], div[class*="error"], div[class*="danger"]');
                if (alertEl) {
                    const alertText = alertEl.innerText ? alertEl.innerText.trim() : "";
                    if (alertText.length > 0 && !alertText.toLowerCase().includes("tip")) {
                        throw new Error(`ChatGPT Web Error: ${alertText}`);
                    }
                }

                // ตรวจสอบสถานะกล่องข้อความ
                const inputNow = findPromptInput();
                const hasText = inputNow && (inputNow.value || inputNow.textContent || "").trim().length > 0;

                // ตรวจสอบกรณี Silent Block: จะถือว่าโดนบล็อกได้ก็ต่อเมื่อ "ยังมีข้อความค้างอยู่ในกล่องพิมพ์" และพยายามส่งเกิน 45 รอบ (~27 วินาที)
                if (retryCycle >= 45 && !isGenerating() && !hasNewResponse) {
                    if (hasText) {
                        const limitStatus = checkAccountRateLimit();
                        console.warn("[ATF Bridge] Send button is blocked / unresponsive! limitStatus:", limitStatus);
                        if (inputNow) clearPromptInput(inputNow); // ล้างกล่องข้อความทิ้งทันที 100% ไม่ให้มีข้อความค้างสะสม
                        throw new Error(limitStatus.isRateLimited ? `ChatGPT Rate Limit Active: ${limitStatus.reason}` : "ChatGPT Send Button Blocked or Unresponsive.");
                    } else {
                        // หากไม่มีข้อความค้างอยู่ในกล่องแล้ว แปลว่าข้อความถูกกดส่งออกไปเรียบร้อยแล้ว
                        console.log("[ATF Bridge] Prompt input is clear (sent). Transitioning to response wait loop.");
                        break;
                    }
                }

                // Active Retry: หากผ่านไปทุกๆ 4 วินาที (retryCycle % 6 == 0) แล้วข้อความยังค้างอยู่ในกล่อง ให้กระตุ้นกดปุ่ม Send ซ้ำ
                if (retryCycle % 6 === 0 && hasText) {
                    const retryBtn = getSendButton();
                    if (retryBtn) {
                        console.log("[ATF Bridge] Active retry triggering Send button...");
                        retryBtn.disabled = false;
                        retryBtn.removeAttribute('disabled');
                        retryBtn.click();
                        const form = inputNow.closest('form');
                        if (form && typeof form.requestSubmit === 'function') {
                            try { form.requestSubmit(); } catch (e) { }
                        }
                    }
                }
            }

            updateStatus("Generating response...", "#8b5cf6");

            // State-Based Generation Wait (No Arbitrary Timeout: รอจนกระทั่งพิมพ์จบสมบูรณ์ 100%)
            let lastText = "";
            let stableCount = 0;
            let idleSecondsWithoutProgress = 0;

            while (true) {
                await new Promise(r => setTimeout(r, 1000));
                const currentText = getLatestAssistantResponse();
                const generating = isGenerating();

                // ตรวจสอบ Error Banner บนหน้าเว็บทันที (เช่น "There was an error generating a response")
                const alertEl = document.querySelector('[role="alert"], div[class*="error"], div[class*="danger"], button[aria-label*="Regenerate"]');
                if (alertEl && !generating && (!currentText || currentText.length < 10)) {
                    const alertText = alertEl.innerText ? alertEl.innerText.trim() : "";
                    if (alertText.length > 0) {
                        throw new Error(`ChatGPT Web Error: ${alertText}`);
                    }
                }

                if (generating) {
                    // หากปุ่ม Stop ยังอยู่ หรือกำลังสตรีม ให้รีเซ็ตตัวนับความนิ่ง
                    stableCount = 0;
                    idleSecondsWithoutProgress = 0;
                    lastText = currentText;
                    continue;
                }

                // หากข้อความยังยาวขึ้นเรื่อยๆ แสดงว่ายังมีการอัปเดต DOM
                if (currentText.length > lastText.length) {
                    lastText = currentText;
                    stableCount = 0;
                    idleSecondsWithoutProgress = 0;
                    continue;
                }

                // หากไม่มีปุ่ม Stop แล้ว และข้อความนิ่งยาวเกิน 30 ตัวอักษร
                if (currentText && currentText.length > 30 && currentText === lastText) {
                    stableCount++;

                    // ตรวจสอบความสมบูรณ์ของโครงสร้าง JSON
                    const trimmed = currentText.trim();
                    const isJsonArray = trimmed.startsWith("[") || trimmed.includes("```json\n[") || trimmed.includes("```\n[");
                    const isJsonComplete = trimmed.endsWith("]") || trimmed.endsWith("```");

                    // ถ้านิ่งครบ 2 วินาที และโครงสร้างปิดสมบูรณ์ (หรือนิ่งครบ 3 วินาทีสำหรับข้อความทั่วไป) -> ถือว่าเสร็จสมบูรณ์ทันที
                    if ((isJsonArray && isJsonComplete && stableCount >= 2) || stableCount >= 3) {
                        console.log("[ATF Bridge] State-Based Completion Confirmed! Response size:", currentText.length);
                        break;
                    }
                } else if (!currentText || currentText.length <= 30) {
                    // กรณีไม่มีข้อความเลยและไม่มีปุ่ม Stop
                    idleSecondsWithoutProgress++;
                    if (idleSecondsWithoutProgress >= 40) {
                        throw new Error("ChatGPT stopped generating without producing any response text.");
                    }
                } else {
                    lastText = currentText;
                    stableCount = 0;
                }
            }

            const finalResponse = getLatestAssistantResponse();
            const limitDetected = checkChatLimitWarning();

            // ตรวจสอบว่าคำตอบว่างเปล่าหรือไม่ ป้องกันส่งค่าว่างกลับไป
            if (!finalResponse || finalResponse.trim().length === 0) {
                const alertEl = document.querySelector('[role="alert"], div[class*="error"], div[class*="danger"], div[class*="warning"]');
                const rawAlert = alertEl ? (alertEl.innerText || "").trim() : "";
                const errMsg = rawAlert.length > 0 ? rawAlert : "ChatGPT returned an empty response or generation was interrupted.";
                throw new Error(errMsg);
            }

            updateStatus("Submitting result...", "#10b981");

            // ส่งผลลัพธ์กลับไปยัง Local Bridge Server พร้อม flag แจ้งเตือนลิมิตแชต
            await sendHttpRequest("POST", "/bridge/result", {
                task_id: task.task_id,
                content: finalResponse,
                status: "done",
                chat_limit_reached: limitDetected
            });

            updateStatus(limitDetected ? "Limit Detected! Need New Chat" : "Ready (Task Completed)", limitDetected ? "#f59e0b" : "#22c55e");
        } catch (err) {
            console.error("[ATF Bridge Error]:", err);
            // ตรวจสอบและล้างกล่องข้อความทิ้งทันทีหากมีข้อความค้างอยู่ เพื่อป้องกันไม่ให้มี Token สะสมเด็ดขาด
            try {
                const lingeringInput = findPromptInput();
                if (lingeringInput) {
                    clearPromptInput(lingeringInput);
                }
            } catch (e) { }

            const safeErrMsg = (err && err.message && err.message.trim().length > 0) ? err.message.trim() : "Unknown ChatGPT Bridge Error";
            const limitCheck = checkAccountRateLimit();
            const isAccountRateLimit = limitCheck.isRateLimited ||
                ["try again after", "too many requests", "rate limit", "usage cap", "usage limit", "คุณถึงขีดจำกัดแล้ว", "send button blocked", "blocked", "silent usage limit active"].some(kw => safeErrMsg.toLowerCase().includes(kw));

            updateStatus(isAccountRateLimit ? "Rate Limited! Sentinel Paused" : `Error: ${safeErrMsg.slice(0, 30)}`, "#ef4444");
            try {
                await sendHttpRequest("POST", "/bridge/result", {
                    task_id: task.task_id,
                    content: "",
                    status: isAccountRateLimit ? "rate_limited" : "error",
                    is_rate_limited: isAccountRateLimit,
                    error: safeErrMsg
                });
            } catch (postErr) {
                console.error("[ATF Bridge Error Report Failed]:", postErr);
            }
        } finally {
            isProcessing = false;
            currentTaskId = null;
        }
    }

    async function pollLoop() {
        if (!isProcessing && !isPaused) {
            try {
                const res = await sendHttpRequest("GET", "/bridge/poll");
                if (res && res.has_task && res.task) {
                    await processTask(res.task);
                } else {
                    updateStatus("Connected & Idle", "#22c55e");
                }
            } catch (err) {
                updateStatus("Bridge Server Offline", "#ef4444");
            }
        }
        setTimeout(pollLoop, POLL_INTERVAL_MS);
    }

    console.log("[ATF] ChatGPT Web Bridge Userscript v1.2 initialized.");
    setTimeout(pollLoop, 1500);
})();
