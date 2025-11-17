"""
DOM结构检查工具 - 用于验证指纹提取方案的可行性

功能:
1. 访问目标网站并加载照片列表
2. 分析照片元素的DOM结构
3. 提取所有可能的唯一标识符
4. 输出详细的结构报告
"""

import asyncio
import json
from playwright.async_api import async_playwright

from config import (
    TARGET_URL,
    HEADLESS,
    TIMEOUT,
    SCROLL_PAUSE_TIME,
    MAX_SCROLL_ATTEMPTS,
    PAGE_RENDER_WAIT,
    PHOTO_ITEM_SELECTOR,
)


async def scroll_to_load_all(page):
    """滚动加载所有照片"""
    print("\n正在滚动加载所有照片...")

    container_selector = "div.photo-content.container"
    container = page.locator(container_selector).first
    await container.wait_for(timeout=10000)

    last_photo_count = 0
    scroll_count = 0
    no_change_count = 0

    while scroll_count < MAX_SCROLL_ATTEMPTS:
        await container.evaluate("(element) => { element.scrollTop = element.scrollHeight; }")
        scroll_count += 1
        await asyncio.sleep(SCROLL_PAUSE_TIME)

        current_photo_count = await page.locator(PHOTO_ITEM_SELECTOR).count()

        if current_photo_count > last_photo_count:
            print(f"  滚动 {scroll_count} 次 - 当前 {current_photo_count} 张照片")
            last_photo_count = current_photo_count
            no_change_count = 0
        else:
            no_change_count += 1
            if no_change_count >= 3:
                print(f"✓ 滚动完成，总计 {current_photo_count} 张照片\n")
                break

    return last_photo_count


async def analyze_photo_element_structure(page):
    """分析照片元素的DOM结构"""

    # 获取前5个照片元素进行分析
    photo_items = await page.locator(PHOTO_ITEM_SELECTOR).all()
    sample_size = min(5, len(photo_items))

    print(f"{'='*80}")
    print(f"照片元素DOM结构分析 (样本: 前{sample_size}个照片)")
    print(f"{'='*80}\n")

    analysis_results = []

    for idx in range(sample_size):
        photo_item = photo_items[idx]

        print(f"【照片 #{idx+1}】")
        print("-" * 80)

        # 1. 获取元素的HTML结构
        outer_html = await photo_item.evaluate("el => el.outerHTML")
        print(f"完整HTML (前500字符):\n{outer_html[:500]}...\n")

        # 2. 提取所有属性
        attributes = await photo_item.evaluate("""
            el => {
                const attrs = {};
                for (let attr of el.attributes) {
                    attrs[attr.name] = attr.value;
                }
                return attrs;
            }
        """)
        print(f"元素属性:")
        for key, value in attributes.items():
            print(f"  {key}: {value}")
        print()

        # 3. 查找缩略图URL
        thumbnail_url = None
        thumbnail_sources = []

        # 尝试从img标签提取
        img_elements = await photo_item.locator("img").all()
        for img in img_elements:
            src = await img.get_attribute("src")
            data_src = await img.get_attribute("data-src")
            if src:
                thumbnail_sources.append(f"img[src]: {src}")
            if data_src:
                thumbnail_sources.append(f"img[data-src]: {data_src}")

        # 尝试从背景图片提取
        bg_style = await photo_item.evaluate("""
            el => {
                const bgElements = el.querySelectorAll('[style*="background"]');
                return Array.from(bgElements).map(e => e.style.backgroundImage || e.style.background);
            }
        """)
        for bg in bg_style:
            if bg:
                thumbnail_sources.append(f"background-image: {bg}")

        print(f"缩略图URL来源:")
        if thumbnail_sources:
            for source in thumbnail_sources:
                print(f"  {source}")
        else:
            print("  ⚠️ 未找到缩略图URL")
        print()

        # 4. 查找data-*属性 (可能包含唯一ID)
        data_attributes = await photo_item.evaluate("""
            el => {
                const dataAttrs = {};
                for (let attr of el.attributes) {
                    if (attr.name.startsWith('data-')) {
                        dataAttrs[attr.name] = attr.value;
                    }
                }
                return dataAttrs;
            }
        """)
        print(f"data-* 属性 (唯一标识符候选):")
        if data_attributes:
            for key, value in data_attributes.items():
                print(f"  {key}: {value}")
        else:
            print("  ⚠️ 未找到data-*属性")
        print()

        # 5. 查找其他可能的唯一标识
        unique_identifiers = await photo_item.evaluate("""
            el => {
                return {
                    id: el.id,
                    class: el.className,
                    aria_label: el.getAttribute('aria-label'),
                    title: el.getAttribute('title'),
                    key: el.getAttribute('key'),
                };
            }
        """)
        print(f"其他可能的唯一标识:")
        for key, value in unique_identifiers.items():
            if value:
                print(f"  {key}: {value}")
        print()

        # 记录分析结果
        analysis_results.append({
            "index": idx,
            "attributes": attributes,
            "data_attributes": data_attributes,
            "thumbnail_sources": thumbnail_sources,
            "unique_identifiers": unique_identifiers,
        })

        print("=" * 80 + "\n")

    return analysis_results


async def generate_fingerprint_recommendation(analysis_results):
    """基于分析结果生成指纹提取建议"""

    print("\n" + "="*80)
    print("指纹提取方案建议")
    print("="*80 + "\n")

    # 统计各种标识符的可用性
    has_thumbnail = sum(1 for r in analysis_results if r['thumbnail_sources']) > 0
    has_data_attrs = sum(1 for r in analysis_results if r['data_attributes']) > 0
    has_id = sum(1 for r in analysis_results if r['unique_identifiers'].get('id')) > 0

    sample_size = len(analysis_results)

    print(f"【统计结果】(基于{sample_size}个样本)")
    print(f"  - 缩略图URL可用: {has_thumbnail}/{sample_size} ({has_thumbnail*100/sample_size:.0f}%)")
    print(f"  - data-*属性可用: {has_data_attrs}/{sample_size} ({has_data_attrs*100/sample_size:.0f}%)")
    print(f"  - id属性可用: {has_id}/{sample_size} ({has_id*100/sample_size:.0f}%)")
    print()

    # 生成推荐方案
    recommendations = []

    if has_thumbnail == sample_size:
        recommendations.append({
            "priority": 1,
            "method": "缩略图URL指纹",
            "description": "所有样本都有缩略图URL，可提取URL中的唯一标识符",
            "implementation": "从img[src]或img[data-src]提取URL，计算MD5或提取ID部分",
            "reliability": "⭐⭐⭐⭐⭐",
        })

    if has_data_attrs == sample_size:
        # 找出最稳定的data-*属性
        common_data_attrs = set(analysis_results[0]['data_attributes'].keys())
        for r in analysis_results[1:]:
            common_data_attrs &= set(r['data_attributes'].keys())

        if common_data_attrs:
            recommendations.append({
                "priority": 2,
                "method": f"data-*属性指纹",
                "description": f"所有样本都有{list(common_data_attrs)}属性",
                "implementation": f"直接读取{list(common_data_attrs)[0]}作为唯一标识",
                "reliability": "⭐⭐⭐⭐⭐",
            })

    if has_id == sample_size:
        recommendations.append({
            "priority": 3,
            "method": "id属性指纹",
            "description": "所有样本都有id属性",
            "implementation": "直接读取id属性作为唯一标识",
            "reliability": "⭐⭐⭐⭐⭐",
        })

    # 降级方案
    if not recommendations:
        recommendations.append({
            "priority": 99,
            "method": "元素索引 + 文件名组合",
            "description": "未找到稳定的唯一标识符，使用组合方案",
            "implementation": "使用元素在列表中的相对位置+文件名生成指纹",
            "reliability": "⭐⭐⭐ (不推荐)",
        })

    print("【推荐方案】")
    for rec in recommendations:
        print(f"\n优先级 {rec['priority']}: {rec['method']}")
        print(f"  描述: {rec['description']}")
        print(f"  实现: {rec['implementation']}")
        print(f"  可靠性: {rec['reliability']}")

    print("\n" + "="*80 + "\n")

    return recommendations


async def main():
    """主程序"""
    print("\n" + "="*80)
    print("PhotoPlus DOM结构检查工具")
    print("="*80 + "\n")
    print(f"目标URL: {TARGET_URL}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(TIMEOUT)

        try:
            # 1. 访问页面
            print("正在访问页面...")
            await page.goto(TARGET_URL, wait_until="networkidle")
            await page.wait_for_timeout(PAGE_RENDER_WAIT)
            print("✓ 页面加载完成\n")

            # 2. 滚动加载所有照片
            total_photos = await scroll_to_load_all(page)

            # 3. 分析DOM结构
            analysis_results = await analyze_photo_element_structure(page)

            # 4. 生成指纹提取建议
            recommendations = await generate_fingerprint_recommendation(analysis_results)

            # 5. 保存详细分析结果
            output_file = "dom_analysis_result.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump({
                    "total_photos": total_photos,
                    "sample_size": len(analysis_results),
                    "analysis_results": analysis_results,
                    "recommendations": recommendations,
                }, f, indent=2, ensure_ascii=False)

            print(f"✓ 详细分析结果已保存到: {output_file}")

        except Exception as e:
            print(f"\n❌ 检查失败: {e}")
            import traceback
            traceback.print_exc()

        finally:
            await browser.close()
            print("\n程序已退出")


if __name__ == "__main__":
    asyncio.run(main())
