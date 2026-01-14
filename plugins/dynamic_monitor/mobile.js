/*
 * 移动端动态页面样式处理脚本
 * 基于HarukaBot的mobile.js实现
 */
async function getMobileStyle(useImageBig = false) {
    // 删除 dom 的对象, 可以自行添加 ( className 需要增加 '.' 为前缀, id 需要增加 '#' 为前缀)
    const deleteDoms = {
        // 关注 dom
        followDoms: [".dyn-header__following", ".easy-follow-btn", ".dyn-orig-author__right"],
        // 分享 dom
        shareDoms: [".dyn-share"],
        // 打开程序 dom
        openAppBtnDoms: [".dynamic-float-btn", ".float-openapp", ".m-dynamic-float-openapp"],
        // 导航 dom
        navDoms: [".m-navbar", ".opus-nav"],
        // 获取更多 dom
        readMoreDoms: [".opus-read-more"],
        // 全屏弹出 Dom
        openAppDialogDoms: [".openapp-dialog"],
        // 评论区 dom
        commentsDoms: [".v-switcher"],
        // 打开商品 dom
        openGoodsDoms: [".bm-link-card-goods__one__action", ".dyn-goods__one__action"],
    }

    // 遍历对象的值, 并将多数组扁平化, 再遍历进行删除操作
    Object.values(deleteDoms).flat(1).forEach(domTag => {
        const deleteDom = document.querySelector(domTag);
        deleteDom && deleteDom.remove();
    })

    // 新版动态需要移除对应 class 达到跳过点击事件, 解除隐藏的目的
    const contentDom = document.querySelector(".opus-module-content");
    contentDom && contentDom.classList.remove("limit");

    // 设置 mopus 的 paddingTop 为 0
    const mOpusDom = document.querySelector(".m-opus");
    if (mOpusDom) {
        mOpusDom.style.paddingTop = "0";
        mOpusDom.style.minHeight = "0";
    }

    // 删除老版动态 .dyn-card 上的字体设置
    const dynCardDom = document.querySelector(".dyn-card");
    if (dynCardDom) {
        dynCardDom.style.fontFamily = "unset";
    }

    // 处理图片大小
    if (!useImageBig) {
        // 缩放图片
        const images = document.querySelectorAll("img");
        images.forEach(img => {
            if (img.clientWidth > 400) {
                img.style.width = "400px";
                img.style.height = "auto";
            }
        });
    }

    // 修复字体和换行问题
    const dyn = document.querySelector(".dyn-card") || document.querySelector(".opus-modules");
    if (dyn) {
        dyn.style.fontFamily = 'Noto Sans CJK SC, sans-serif';
        dyn.style.overflowWrap = 'break-word';
    }

    // 标记样式处理完成
    window.mobileStyleComplete = true;
}

function setFont(font = "", fontSource = "local") {
    // 字体加载逻辑
    const needLoadFontList = [
        {
            fontUrl: "https://cdn.jsdelivr.net/gh/irozhi/HarmonyOS-Sans/HarmonyOS_Sans_SC/HarmonyOS_Sans_SC_Medium.woff2",
            fontName: "HarmonyOS Sans SC Medium",
        },
        {
            fontUrl: "https://cdn.jsdelivr.net/gh/irozhi/HarmonyOS-Sans/HarmonyOS_Sans_SC/HarmonyOS_Sans_SC_Regular.woff2",
            fontUrl: "https://cdn.jsdelivr.net/gh/irozhi/HarmonyOS-Sans/HarmonyOS_Sans_SC/HarmonyOS_Sans_SC_Regular.woff2",
            fontName: "HarmonyOS Sans SC Regular",
        },
    ];

    if (fontSource === "remote") {
        // 加载远程字体
        needLoadFontList.forEach(async (fontInfo) => {
            try {
                const fontFace = new FontFace(fontInfo.fontName, `url(${fontInfo.fontUrl})`);
                await fontFace.load();
                document.fonts.add(fontFace);
            } catch (e) {
                console.warn(`Failed to load font ${fontInfo.fontName}:`, e);
            }
        });
    }

    // 设置字体
    const fontFamily = font || "HarmonyOS Sans SC, Noto Sans CJK SC, sans-serif";
    document.body.style.fontFamily = fontFamily;

    // 标记字体加载完成
    window.fontsLoaded = true;
}

async function imageComplete() {
    // 等待所有图片加载完成
    const images = document.querySelectorAll("img");
    const promises = Array.from(images).map(img => {
        return new Promise((resolve) => {
            if (img.complete) {
                resolve();
            } else {
                img.addEventListener('load', resolve);
                img.addEventListener('error', resolve);
            }
        });
    });

    await Promise.all(promises);
    window.imageComplete = true;
}

async function fontsLoaded() {
    // 等待字体加载完成
    if (document.fonts && document.fonts.ready) {
        await document.fonts.ready;
    }
    window.fontsLoaded = true;
}

// 默认执行一次样式处理
getMobileStyle();