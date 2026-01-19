/*
 * B站动态页面样式处理脚本
 * 基于HarukaBot的mobile.js实现
 */

/**
 * 清理不需要的DOM元素
 */
function cleanUpDOM() {
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
    };

    // 遍历对象的值, 并将多数组扁平化, 再遍历进行删除操作
    Object.values(deleteDoms).flat(1).forEach(domTag => {
        const deleteDom = document.querySelector(domTag);
        deleteDom && deleteDom.remove();
    });
}

/**
 * 优化页面布局
 */
function optimizeLayout() {
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
}

/**
 * 处理图片大小优化
 * @param {boolean} useImageBig - 是否使用大图
 */
function optimizeImages(useImageBig = false) {
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
}

/**
 * 设置基础排版样式
 */
function setupTypography() {
    // 修复字体和换行问题
    const dyn = document.querySelector(".dyn-card") || document.querySelector(".opus-modules");
    if (dyn) {
        // 对齐Windows默认字体栈：Segoe UI -> Microsoft YaHei/Meiryo/Malgun Gothic -> Segoe UI Emoji
        // Linux对应：DejaVu Sans -> Noto Sans CJK -> Noto Color Emoji
        dyn.style.fontFamily = '"Segoe UI", "DejaVu Sans", "Microsoft YaHei", "Meiryo", "Malgun Gothic", "Noto Sans CJK SC", "Noto Sans CJK JP", "Noto Sans CJK KR", "Noto Color Emoji", "Segoe UI Emoji", sans-serif';
        dyn.style.overflowWrap = 'break-word';
        dyn.style.wordBreak = 'break-word';
        dyn.style.fontVariantLigatures = 'normal';
        dyn.style.textRendering = 'optimizeLegibility';
        // 确保数字使用半角形式
        dyn.style.fontVariantNumeric = 'normal';
    }
}

/**
 * 优化文本元素字体
 */
function optimizeTextElements() {
    // 确保所有文本元素都有正确的字体
    const textElements = document.querySelectorAll('p, span, div, h1, h2, h3, h4, h5, h6, em, strong, b, i, time, .bili-dyn-time, .dyn-time');
    textElements.forEach(el => {
        if (getComputedStyle(el).fontFamily.includes('Segoe UI') === false) {
            // 对齐Windows默认字体栈
            el.style.fontFamily = '"Segoe UI", "DejaVu Sans", "Microsoft YaHei", "Meiryo", "Malgun Gothic", "Noto Sans CJK SC", "Noto Sans CJK JP", "Noto Sans CJK KR", "Noto Color Emoji", "Segoe UI Emoji", sans-serif';
            el.style.fontVariantNumeric = 'normal';
        }
    });
}

/**
 * 应用B站动态样式优化（向后兼容函数）
 * @param {boolean} useImageBig - 是否使用大图
 */
async function getMobileStyle(useImageBig = false) {
    cleanUpDOM();
    optimizeLayout();
    optimizeImages(useImageBig);
    setupTypography();
    optimizeTextElements();

    // 标记样式处理完成
    window.bilibiliStyleComplete = true;
}

/**
 * 获取标准字体族
 * @param {string} customFont - 自定义字体
 * @returns {string} 标准字体族字符串
 */
function getStandardFontFamily(customFont = "") {
    // 对齐Windows默认字体栈：Segoe UI -> Microsoft YaHei/Meiryo/Malgun Gothic -> Segoe UI Emoji
    // Linux对应：DejaVu Sans -> Noto Sans CJK -> Noto Color Emoji
    return customFont || '"Segoe UI", "DejaVu Sans", "Microsoft YaHei", "Meiryo", "Malgun Gothic", "Noto Sans CJK SC", "Noto Sans CJK JP", "Noto Sans CJK KR", "Noto Color Emoji", "Segoe UI Emoji", sans-serif';
}

/**
 * 设置全局字体样式
 * @param {string} font - 自定义字体
 * @param {string} fontSource - 字体来源
 */
function setFont(font = "", fontSource = "local") {
    const fontFamily = getStandardFontFamily(font);

    // 设置全局字体
    document.body.style.fontFamily = fontFamily;
    document.body.style.fontVariantNumeric = 'normal';
    document.documentElement.style.fontFamily = fontFamily;
    document.documentElement.style.fontVariantNumeric = 'normal';

    // 确保动态内容区域也使用正确字体
    const dynElements = document.querySelectorAll('.card, .dynamic-card, .bili-dyn-item__card, .dyn-card, .opus-modules, .dyn-header, .dyn-content, .opus-module-content, .bili-dyn-time, .dyn-time, time');
    dynElements.forEach(el => {
        el.style.fontFamily = fontFamily;
        el.style.fontVariantLigatures = 'normal';
        el.style.textRendering = 'optimizeLegibility';
        el.style.fontFeatureSettings = '"liga" off';
        // 确保数字使用半角形式
        el.style.fontVariantNumeric = 'normal';
        // 确保emoji正确显示
        el.style.fontVariantEmoji = 'emoji';
    });

    // 特别处理时间戳元素，确保数字正确显示
    optimizeTimeElements();

    // 标记字体加载完成
    window.fontsLoaded = true;
    console.log('字体设置完成:', fontFamily);
}

/**
 * 特别优化时间戳元素
 */
function optimizeTimeElements() {
    const timeElements = document.querySelectorAll('time, .bili-dyn-time, .dyn-time, [class*="time"], [class*="Time"]');
    timeElements.forEach(el => {
        el.style.fontFamily = '"Segoe UI", "DejaVu Sans", monospace, sans-serif';
        el.style.fontVariantNumeric = 'normal';
        // 移除可能导致数字显示异常的等宽数字设置
        // el.style.fontFeatureSettings = '"tnum" 1, "lnum" 1';
    });
}


// 默认执行一次样式处理
getMobileStyle();