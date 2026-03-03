"""
Smart Money Address Mining Skill

功能描述:
    独立的聪明钱地址挖掘工具，支持两种输入方式：
    1. 从PumpFun API自动抓取已毕业代币
    2. 用户手动提供代币地址列表

    复用main.py的核心分析逻辑，但移除已失效的90天/30天盈利和交易数字段。
    输出JSON格式结果，便于后续Telegram集成。

筛选条件:
    - TOP 5平均盈利率 > 0
    - TOP 10平均盈利率 > 0
    - 整体胜率 >= 10%
    - 平均盈利 >= 500 USDT
    - 平均盈利率 >= 0%

使用方法:
    # 从PumpFun抓取
    python smart_money_miner.py --pumpfun --limit 20

    # 手动提供地址
    python smart_money_miner.py --tokens token1,token2,token3

    # 混合使用
    python smart_money_miner.py --tokens token1 --pumpfun --limit 10
"""

import requests
import time
import json
import os
import argparse
from datetime import datetime
from typing import List, Dict, Optional, Set

# --- 配置参数 ---

# PumpFun API
PUMPFUN_API_URL = "https://frontend-api-v3.pump.fun/coins"
DEFAULT_PUMPFUN_LIMIT = 20
PUMPFUN_SORT = "last_trade_timestamp"
PUMPFUN_ORDER = "DESC"

# OKX API 基础 URL
API_BASE_URL_1 = "https://web3.okx.com/priapi/v1/dx/market/v2/pnl/top-trader/ranking-list"
API_BASE_URL_2 = "https://web3.okx.com/priapi/v1/dx/market/v2/pnl/token-list"
API_BASE_URL_4 = "https://web3.okx.com/priapi/v1/dx/market/v2/pnl/token-list"

SOL_CHAIN_ID = 501  # Solana 链 ID
BSC_CHAIN_ID = 56   # BNB Chain (BSC) 链 ID
MAX_RETRIES = 3  # API 请求最大重试次数
RETRY_DELAY = 5  # 重试间隔时间（秒）

# Four Meme API (BSC 上类似 PumpFun 的平台)
FOUR_MEME_API_URL = "https://four.meme/meme-api/v1/private/token/query"
DEFAULT_FOURMEME_LIMIT = 20

# Binance AI Narrative API
BINANCE_AI_NARRATIVE_URL = "https://web3.binance.com/bapi/defi/v1/public/wallet-direct/buw/wallet/token/ai/narrative/query"

# 筛选阈值（移除90天/30天相关）
TOP5_MIN_PROFIT_RATE = 0.0
TOP10_MIN_PROFIT_RATE = 0.0
MIN_WIN_RATE = 10.0  # 10%
MIN_AVG_PROFIT_USDT = 500
MIN_AVG_PROFIT_RATE = 0.0

# 输出文件
OUTPUT_JSON_FILE = "smart_money_results.json"
SKIP_ADDRESSES_FILE = "skip_addresses.json"  # 可选


# --- 辅助函数 ---

def get_current_timestamp_ms():
    """生成当前毫秒级时间戳"""
    return int(time.time() * 1000)


def make_api_request(url, params, max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY):
    """
    通用 API 请求函数，包含重试逻辑。
    """
    for attempt in range(max_retries):
        try:
            params['t'] = get_current_timestamp_ms()
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            api_data = response.json()

            if api_data.get("code") == 0:
                return api_data["data"]
            else:
                print(
                    f"API 返回非零代码 (尝试 {attempt + 1}/{max_retries}): {api_data.get('code')}, Msg: {api_data.get('msg')}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        except requests.exceptions.Timeout:
            print(f"API 请求超时 (尝试 {attempt + 1}/{max_retries}): {url}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
        except requests.exceptions.RequestException as e:
            print(f"API 请求失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
        except json.JSONDecodeError as e:
            print(f"API 响应 JSON 解析失败 (尝试 {attempt + 1}/{max_retries}): {e}")
            break
        except Exception as e:
            print(f"发生未知错误 (尝试 {attempt + 1}/{max_retries}): {e}")
            break
    print(f"所有重试均失败，无法从 {url} 获取数据。")
    return None


def load_skip_addresses(file_path: str = SKIP_ADDRESSES_FILE) -> Set[str]:
    """
    从JSON文件加载跳过地址列表
    """
    if not os.path.exists(file_path):
        print(f"跳过地址文件 '{file_path}' 不存在，将不跳过任何地址。")
        return set()

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            skip_addresses = set(data.get("skip_addresses", []))
            print(f"已加载 {len(skip_addresses)} 个跳过地址。")
            return skip_addresses
    except Exception as e:
        print(f"加载跳过地址文件失败: {e}")
        return set()


def detect_chain_id(address: str) -> int:
    """根据地址格式自动检测链: 0x前缀 = BSC(56), 否则 = Solana(501)"""
    if address.strip().lower().startswith("0x"):
        return BSC_CHAIN_ID
    return SOL_CHAIN_ID


# --- PumpFun API 集成 ---

def fetch_pumpfun_tokens(limit: int = DEFAULT_PUMPFUN_LIMIT, offset: int = 0) -> List[Dict]:
    """
    从PumpFun API获取已毕业代币列表

    返回格式:
    [
        {
            "mint": "token_address",
            "name": "token_name",
            "symbol": "token_symbol",
            "market_cap": 123456,
            "created_timestamp": 1234567890
        },
        ...
    ]
    """
    print(f"正在从PumpFun API获取已毕业代币 (limit={limit}, offset={offset})...")

    params = {
        "complete": "true",
        "sort": PUMPFUN_SORT,
        "order": PUMPFUN_ORDER,
        "limit": limit,
        "offset": offset
    }

    try:
        response = requests.get(PUMPFUN_API_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()

        if isinstance(data, list):
            tokens = []
            for item in data:
                tokens.append({
                    "mint": item.get("mint"),
                    "name": item.get("name"),
                    "symbol": item.get("symbol"),
                    "market_cap": item.get("market_cap"),
                    "created_timestamp": item.get("created_timestamp")
                })
            print(f"成功获取 {len(tokens)} 个已毕业代币。")
            return tokens
        else:
            print(f"PumpFun API 返回格式异常: {data}")
            return []
    except Exception as e:
        print(f"从PumpFun API获取代币失败: {e}")
        return []


# --- Four Meme API 集成 (BSC) ---

def fetch_four_meme_tokens(limit: int = DEFAULT_FOURMEME_LIMIT) -> List[Dict]:
    """
    从Four Meme API获取最近已毕业代币列表 (BSC链)

    返回格式与 fetch_pumpfun_tokens 一致:
    [
        {
            "mint": "0x...",
            "name": "token_name",
            "symbol": "token_symbol",
            "web_url": "...",
            "twitter_url": "..."
        },
        ...
    ]
    """
    print(f"正在从Four Meme API获取BSC已毕业代币 (limit={limit})...")

    all_items = []
    seen_addresses = set()
    page_size = min(limit, 30)
    max_pages = (limit + page_size - 1) // page_size

    for page_index in range(1, max_pages + 1):
        params = {
            "orderBy": "TimeDesc",
            "tokenName": "",
            "listedPancake": "true",
            "pageIndex": str(page_index),
            "pageSize": str(page_size),
            "symbol": "",
            "labels": "",
        }
        try:
            response = requests.get(FOUR_MEME_API_URL, params=params, timeout=15)
            data = response.json()
        except Exception as e:
            print(f"获取Four Meme列表失败: {e}")
            break

        token_list = data.get("data") or []
        if not token_list:
            break

        for raw in token_list:
            address = (raw.get("address") or "").strip().lower()
            if not address or address in seen_addresses:
                continue
            seen_addresses.add(address)

            short_name = (raw.get("shortName") or raw.get("name") or "").strip()
            symbol = (raw.get("symbol") or short_name).strip()
            web_url = (raw.get("webUrl") or "").strip()
            twitter_url = (raw.get("twitterUrl") or "").strip()

            all_items.append({
                "mint": address,
                "name": short_name,
                "symbol": symbol,
                "web_url": web_url,
                "twitter_url": twitter_url,
            })

            if len(all_items) >= limit:
                break

        if len(all_items) >= limit:
            break
        time.sleep(0.5)

    print(f"成功获取 {len(all_items)} 个BSC已毕业代币。")
    return all_items[:limit]


def is_binance_token(web_url: str, twitter_url: str) -> bool:
    """检测代币是否与Binance相关"""
    text = f"{web_url} {twitter_url}".lower()
    keywords = ["binance", "bnbchain", "_richardteng", "nina_rong"]
    return any(k in text for k in keywords)


def fetch_binance_ai_narrative(address: str) -> Optional[str]:
    """获取币安AI叙事内容"""
    params = {
        "chainId": "56",
        "contractAddress": address.lower()
    }
    try:
        resp = requests.get(BINANCE_AI_NARRATIVE_URL, params=params, timeout=15)
        data = resp.json()
        if data.get("code") == "000000" and data.get("success"):
            return data.get("data", {}).get("text", {}).get("cn")
    except Exception as e:
        print(f"获取币安AI叙事失败 ({address}): {e}")
    return None


# --- OKX API 封装函数（复用自main.py） ---

def fetch_top_traders(token_contract_address: str, chain_id: int) -> List[Dict]:
    """
    调用 API 1: 获取指定代币的 TOP 100 盈利地址。
    """
    print(f"正在获取代币 {token_contract_address} 的 TOP 100 盈利地址...")
    params = {
        "tokenContractAddress": token_contract_address,
        "chainId": chain_id,
        "limit": 100,
        "offset": 0
    }
    data = make_api_request(API_BASE_URL_1, params)

    # API 可能返回 'rankingList' 或 'list' 字段
    if data:
        if "rankingList" in data:
            print(f"成功获取 {len(data['rankingList'])} 个盈利地址。")
            return data["rankingList"]
        elif "list" in data:
            print(f"成功获取 {len(data['list'])} 个盈利地址。")
            return data["list"]
        else:
            print(f"获取代币 {token_contract_address} 的 TOP 盈利地址失败。")
            print(f"API 返回数据键: {list(data.keys())}")
            return []
    else:
        print(f"获取代币 {token_contract_address} 的 TOP 盈利地址失败 - API 无返回数据。")
        return []


def fetch_token_pnl_summary(wallet_address: str, chain_id: int) -> Dict:
    """
    调用 API 4: 获取钱包的 TOP 5 和 TOP 10 代币平均盈利率。
    """
    print(f"正在获取钱包 {wallet_address} 的 TOP 5/10 盈利均值...")
    params = {
        "walletAddress": wallet_address,
        "chainId": chain_id,
        "isAsc": "false",
        "sortType": 1,
        "offset": 0,
        "limit": 10
    }
    data = make_api_request(API_BASE_URL_4, params)

    if data and "tokenList" in data:
        token_list = data["tokenList"]
        pnl_percentages = []

        for token in token_list:
            try:
                pnl_percentages.append(float(token.get("totalPnlPercentage", 0)))
            except (ValueError, TypeError):
                pnl_percentages.append(0.0)

        avg_top5 = float('nan')
        if pnl_percentages:
            count_top5 = min(len(pnl_percentages), 5)
            if count_top5 > 0:
                avg_top5 = round(sum(pnl_percentages[:count_top5]) / count_top5, 4)

        avg_top10 = float('nan')
        if pnl_percentages:
            count_top10 = min(len(pnl_percentages), 10)
            if count_top10 > 0:
                avg_top10 = round(sum(pnl_percentages[:count_top10]) / count_top10, 4)

        print(f"成功获取钱包 {wallet_address} 的盈利均值: Top5Avg={avg_top5}, Top10Avg={avg_top10}")
        return {"avgPnlPercentage_top5": avg_top5, "avgPnlPercentage_top10": avg_top10}
    else:
        print(f"API 4 返回数据异常 for {wallet_address}.")
    return {"avgPnlPercentage_top5": float('nan'), "avgPnlPercentage_top10": float('nan')}


def fetch_token_list_paged(wallet_address: str, chain_id: int, max_pages: int = 10, limit_per_page: int = 50) -> List[Dict]:
    """
    调用 API 2: 分页获取指定钱包的代币盈利详情。
    """
    print(f"正在分页获取钱包 {wallet_address} 的代币盈利详情...")
    all_tokens = []
    offset = 0
    has_next = True
    page_count = 0

    while has_next and page_count < max_pages:
        params = {
            "walletAddress": wallet_address,
            "chainId": chain_id,
            "isAsc": "false",
            "sortType": 1,
            "offset": offset,
            "limit": limit_per_page
        }
        data = make_api_request(API_BASE_URL_2, params)

        if data and "tokenList" in data:
            all_tokens.extend(data["tokenList"])
            has_next = data.get("hasNext", False)
            offset = data.get("offset", offset + limit_per_page)
            page_count += 1
            print(f"已获取钱包 {wallet_address} 第 {page_count} 页数据，当前总代币数：{len(all_tokens)}")
            if has_next and page_count < max_pages:
                time.sleep(0.5)
        else:
            print(f"获取钱包 {wallet_address} 代币列表时遇到问题或无更多数据。")
            break

    print(f"完成钱包 {wallet_address} 的代币盈利详情获取，共 {len(all_tokens)} 条代币记录。")
    return all_tokens


# --- 核心分析逻辑 ---

def analyze_wallet_address(wallet_address: str, chain_id: int, token_info: Optional[Dict] = None) -> Optional[Dict]:
    """
    分析单个钱包地址，返回分析结果

    参数:
        wallet_address: 钱包地址
        chain_id: 链ID (501=Solana, 56=BSC)
        token_info: 可选，代币元数据 (含 web_url, twitter_url 等，用于BSC分析)
    """
    print(f"\n--- 正在分析地址: {wallet_address} ---")

    chain_name = "bsc" if chain_id == BSC_CHAIN_ID else "sol"
    result = {
        "wallet_address": wallet_address,
        "chain": chain_name,
        "top5_avg_profit_rate": None,
        "top10_avg_profit_rate": None,
        "overall_win_rate": None,
        "average_profit_usdt": None,
        "average_profit_rate": None,
        "total_tokens_traded": None,
        "passed_filter": False
    }

    # 1. 获取 TOP 5/10 平均盈利率
    pnl_summary = fetch_token_pnl_summary(wallet_address, chain_id)
    avg_pnl_top5 = pnl_summary.get("avgPnlPercentage_top5")
    avg_pnl_top10 = pnl_summary.get("avgPnlPercentage_top10")

    result["top5_avg_profit_rate"] = avg_pnl_top5
    result["top10_avg_profit_rate"] = avg_pnl_top10

    # 检查 TOP 5/10 盈利率筛选条件
    import math
    if math.isnan(avg_pnl_top5) or math.isnan(avg_pnl_top10):
        print(f"地址 {wallet_address} 的 TOP 5/10 数据无效。")
        return result

    if avg_pnl_top5 <= TOP5_MIN_PROFIT_RATE or avg_pnl_top10 <= TOP10_MIN_PROFIT_RATE:
        print(f"地址 {wallet_address} 未通过 TOP 盈利率筛选 (TOP5: {avg_pnl_top5:.2f}, TOP10: {avg_pnl_top10:.2f})。")
        return result

    # 2. 获取详细代币列表并计算统计数据
    token_list_details = fetch_token_list_paged(wallet_address, chain_id, max_pages=10)

    if not token_list_details:
        print(f"地址 {wallet_address} 无代币交易记录。")
        return result

    total_pnl_sum = 0.0
    total_pnl_percentage_sum = 0.0
    positive_pnl_count = 0
    processed_tokens_count = 0

    for token in token_list_details:
        try:
            token_total_pnl = float(token.get("totalPnl", 0))
            token_total_pnl_percentage = float(token.get("totalPnlPercentage", 0))

            total_pnl_sum += token_total_pnl
            total_pnl_percentage_sum += token_total_pnl_percentage
            processed_tokens_count += 1

            if token_total_pnl > 0:
                positive_pnl_count += 1

        except (ValueError, TypeError) as e:
            print(f"处理代币数据时发生类型转换错误: {e}")
            continue

    # 计算各项均值和胜率
    avg_pnl = total_pnl_sum / processed_tokens_count if processed_tokens_count > 0 else 0
    avg_pnl_percentage = total_pnl_percentage_sum / processed_tokens_count if processed_tokens_count > 0 else 0
    win_rate = (positive_pnl_count / processed_tokens_count * 100) if processed_tokens_count > 0 else 0

    result["overall_win_rate"] = round(win_rate, 2)
    result["average_profit_usdt"] = round(avg_pnl, 2)
    result["average_profit_rate"] = round(avg_pnl_percentage, 2)
    result["total_tokens_traded"] = processed_tokens_count

    # 3. 最终筛选
    if win_rate < MIN_WIN_RATE:
        print(f"地址 {wallet_address} 未通过筛选：胜率 ({win_rate:.2f}%) 低于 {MIN_WIN_RATE}%。")
        return result
    elif avg_pnl < MIN_AVG_PROFIT_USDT:
        print(f"地址 {wallet_address} 未通过筛选：平均盈利 ({avg_pnl:.2f}) 低于 {MIN_AVG_PROFIT_USDT}。")
        return result
    elif avg_pnl_percentage < MIN_AVG_PROFIT_RATE:
        print(f"地址 {wallet_address} 未通过筛选：平均盈利率 ({avg_pnl_percentage:.2f}%) 低于 {MIN_AVG_PROFIT_RATE}%。")
        return result

    result["passed_filter"] = True
    print(f"✓ 地址 {wallet_address} 通过所有筛选条件！")

    # BSC 特有: 检测是否为Binance相关代币，获取AI叙事
    if chain_id == BSC_CHAIN_ID and token_info:
        web_url = token_info.get("web_url", "")
        twitter_url = token_info.get("twitter_url", "")
        if web_url or twitter_url:
            result["is_binance"] = is_binance_token(web_url, twitter_url)
        token_address = token_info.get("mint", "")
        if token_address:
            narrative = fetch_binance_ai_narrative(token_address)
            if narrative:
                result["ai_narrative"] = narrative

    return result


def run_smart_money_analysis(
    token_addresses: Optional[List[str]] = None,
    fetch_from_pumpfun: bool = False,
    pumpfun_limit: int = DEFAULT_PUMPFUN_LIMIT,
    fetch_from_fourmeme: bool = False,
    fourmeme_limit: int = DEFAULT_FOURMEME_LIMIT,
    skip_addresses_file: Optional[str] = SKIP_ADDRESSES_FILE
) -> Dict:
    """
    运行聪明钱地址挖掘分析

    参数:
        token_addresses: 用户提供的代币地址列表（可选）
        fetch_from_pumpfun: 是否从PumpFun抓取（可选）
        pumpfun_limit: 从PumpFun抓取的数量（默认20）
        fetch_from_fourmeme: 是否从Four Meme抓取BSC代币（可选）
        fourmeme_limit: 从Four Meme抓取的数量（默认20）
        skip_addresses_file: 跳过地址文件路径（可选）
    """
    print("=" * 60)
    print("聪明钱地址挖掘系统启动")
    print("=" * 60)

    # 确定数据源
    sources = []
    all_token_addresses = []
    token_info_map = {}  # 代币地址 -> 代币元数据 (用于BSC的binance检测和AI叙事)

    # 1. 从PumpFun获取代币
    if fetch_from_pumpfun:
        pumpfun_tokens = fetch_pumpfun_tokens(limit=pumpfun_limit)
        pumpfun_addresses = [token["mint"] for token in pumpfun_tokens if token.get("mint")]
        all_token_addresses.extend(pumpfun_addresses)
        print(f"从PumpFun获取了 {len(pumpfun_addresses)} 个代币地址。")
        sources.append("pumpfun")

    # 2. 从Four Meme获取BSC代币
    if fetch_from_fourmeme:
        fourmeme_tokens = fetch_four_meme_tokens(limit=fourmeme_limit)
        for token in fourmeme_tokens:
            mint = token.get("mint")
            if mint:
                all_token_addresses.append(mint)
                token_info_map[mint] = token
        print(f"从Four Meme获取了 {len(fourmeme_tokens)} 个BSC代币地址。")
        sources.append("fourmeme")

    # 3. 添加用户手动提供的代币
    if token_addresses:
        all_token_addresses.extend(token_addresses)
        print(f"用户提供了 {len(token_addresses)} 个代币地址。")
        sources.append("manual")

    source = "+".join(sources) if sources else "manual"

    if not all_token_addresses:
        print("错误：未提供任何代币地址，请使用 --tokens、--pumpfun 或 --fourmeme 参数。")
        return {
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "tokens_analyzed": 0,
            "total_addresses_found": 0,
            "filtered_addresses_count": 0,
            "filtered_addresses": [],
            "full_data": []
        }

    # 去重
    all_token_addresses = list(set(all_token_addresses))
    print(f"\n总共需要分析 {len(all_token_addresses)} 个代币。")

    # 3. 加载跳过地址
    skip_addresses = load_skip_addresses(skip_addresses_file) if skip_addresses_file else set()

    # 4. 获取所有代币的 TOP 100 盈利地址
    all_wallet_addresses = set()
    token_source_map = {}  # 记录每个地址来自哪些代币

    for i, token_address in enumerate(all_token_addresses):
        print(f"\n[{i + 1}/{len(all_token_addresses)}] 处理代币: {token_address}")
        top_traders = fetch_top_traders(token_address, detect_chain_id(token_address))

        for trader in top_traders:
            wallet_addr = trader.get("holderWalletAddress")
            if wallet_addr:
                all_wallet_addresses.add(wallet_addr)
                if wallet_addr not in token_source_map:
                    token_source_map[wallet_addr] = []
                token_source_map[wallet_addr].append(token_address)

        time.sleep(0.5)  # 避免请求过快

    print(f"\n从 {len(all_token_addresses)} 个代币中共获取到 {len(all_wallet_addresses)} 个独立地址。")

    # 5. 移除跳过地址
    processable_addresses = [addr for addr in all_wallet_addresses if addr not in skip_addresses]
    print(f"移除跳过地址后，剩余 {len(processable_addresses)} 个地址待分析。")

    if not processable_addresses:
        print("所有地址均已被跳过或无有效地址，程序结束。")
        return {
            "timestamp": datetime.now().isoformat(),
            "source": source,
            "tokens_analyzed": len(all_token_addresses),
            "total_addresses_found": len(all_wallet_addresses),
            "filtered_addresses_count": 0,
            "filtered_addresses": [],
            "full_data": []
        }

    # 6. 分析每个地址
    all_results = []
    filtered_results = []

    print("\n" + "=" * 60)
    print("开始地址分析")
    print("=" * 60)

    for i, wallet_address in enumerate(processable_addresses):
        print(f"\n[{i + 1}/{len(processable_addresses)}] 分析地址: {wallet_address}")

        chain_id = detect_chain_id(wallet_address)
        # 查找该钱包关联的代币元数据 (用于BSC分析)
        wallet_token_info = None
        if chain_id == BSC_CHAIN_ID:
            source_tokens = token_source_map.get(wallet_address, [])
            for src_token in source_tokens:
                if src_token in token_info_map:
                    wallet_token_info = token_info_map[src_token]
                    break

        result = analyze_wallet_address(wallet_address, chain_id, token_info=wallet_token_info)

        if result:
            # 添加来源代币信息
            result["source_tokens"] = token_source_map.get(wallet_address, [])
            all_results.append(result)

            if result["passed_filter"]:
                filtered_results.append(result)

        time.sleep(0.5)  # 避免请求过快

    # 7. 生成输出结果
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "source": source,
        "tokens_analyzed": len(all_token_addresses),
        "total_addresses_found": len(all_wallet_addresses),
        "filtered_addresses_count": len(filtered_results),
        "filtered_addresses": filtered_results,
        "full_data": all_results
    }

    # 8. 保存到JSON文件
    try:
        with open(OUTPUT_JSON_FILE, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        print(f"\n结果已保存到: {OUTPUT_JSON_FILE}")
    except Exception as e:
        print(f"保存JSON文件失败: {e}")

    # 9. 打印摘要
    print("\n" + "=" * 60)
    print("分析完成")
    print("=" * 60)
    print(f"分析代币数: {len(all_token_addresses)}")
    print(f"发现地址数: {len(all_wallet_addresses)}")
    print(f"分析地址数: {len(processable_addresses)}")
    print(f"通过筛选数: {len(filtered_results)}")
    print(f"筛选通过率: {len(filtered_results) / len(processable_addresses) * 100:.2f}%" if processable_addresses else "N/A")
    print("=" * 60)

    return output_data


# --- 命令行接口 ---

def main():
    parser = argparse.ArgumentParser(
        description="Smart Money Address Mining Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 从PumpFun抓取20个代币 (Solana)
  python smart_money_miner.py --pumpfun --limit 20

  # 从Four Meme抓取10个代币 (BSC)
  python smart_money_miner.py --fourmeme --fourmeme-limit 10

  # 手动提供代币地址 (自动检测链)
  python smart_money_miner.py --tokens token1,token2,0xABC123

  # 混合使用
  python smart_money_miner.py --tokens token1 --pumpfun --limit 10 --fourmeme

  # 测试API连接
  python smart_money_miner.py --test-pumpfun
  python smart_money_miner.py --test-fourmeme
        """
    )

    parser.add_argument(
        '--tokens',
        type=str,
        help='逗号分隔的代币地址列表，例如: token1,token2,0xABC123'
    )

    parser.add_argument(
        '--pumpfun',
        action='store_true',
        help='从PumpFun API抓取已毕业代币 (Solana)'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=DEFAULT_PUMPFUN_LIMIT,
        help=f'从PumpFun抓取的代币数量 (默认: {DEFAULT_PUMPFUN_LIMIT})'
    )

    parser.add_argument(
        '--fourmeme',
        action='store_true',
        help='从Four Meme API抓取已毕业代币 (BSC)'
    )

    parser.add_argument(
        '--fourmeme-limit',
        type=int,
        default=DEFAULT_FOURMEME_LIMIT,
        help=f'从Four Meme抓取的代币数量 (默认: {DEFAULT_FOURMEME_LIMIT})'
    )

    parser.add_argument(
        '--skip-file',
        type=str,
        default=SKIP_ADDRESSES_FILE,
        help=f'跳过地址JSON文件路径 (默认: {SKIP_ADDRESSES_FILE})'
    )

    parser.add_argument(
        '--test-pumpfun',
        action='store_true',
        help='测试PumpFun API连接'
    )

    parser.add_argument(
        '--test-fourmeme',
        action='store_true',
        help='测试Four Meme API连接'
    )

    args = parser.parse_args()

    # 测试模式
    if args.test_pumpfun:
        print("测试PumpFun API连接...")
        tokens = fetch_pumpfun_tokens(limit=5)
        if tokens:
            print(f"\n成功获取 {len(tokens)} 个代币:")
            for i, token in enumerate(tokens, 1):
                name = token['name'].encode('utf-8', errors='replace').decode('utf-8')
                symbol = token['symbol'].encode('utf-8', errors='replace').decode('utf-8')
                try:
                    print(f"{i}. {symbol} ({name}) - {token['mint']}")
                except UnicodeEncodeError:
                    print(f"{i}. {token['mint']}")
        else:
            print("测试失败，无法获取代币数据。")
        return

    if args.test_fourmeme:
        print("测试Four Meme API连接...")
        tokens = fetch_four_meme_tokens(limit=5)
        if tokens:
            print(f"\n成功获取 {len(tokens)} 个BSC代币:")
            for i, token in enumerate(tokens, 1):
                name = token['name'].encode('utf-8', errors='replace').decode('utf-8')
                symbol = token['symbol'].encode('utf-8', errors='replace').decode('utf-8')
                try:
                    print(f"{i}. {symbol} ({name}) - {token['mint']}")
                except UnicodeEncodeError:
                    print(f"{i}. {token['mint']}")
        else:
            print("测试失败，无法获取代币数据。")
        return

    # 解析代币地址
    token_addresses = None
    if args.tokens:
        token_addresses = [addr.strip() for addr in args.tokens.split(',') if addr.strip()]

    # 运行分析
    if not args.pumpfun and not args.fourmeme and not token_addresses:
        parser.print_help()
        print("\n错误：请至少提供 --tokens、--pumpfun 或 --fourmeme 参数之一。")
        return

    run_smart_money_analysis(
        token_addresses=token_addresses,
        fetch_from_pumpfun=args.pumpfun,
        pumpfun_limit=args.limit,
        fetch_from_fourmeme=args.fourmeme,
        fourmeme_limit=args.fourmeme_limit,
        skip_addresses_file=args.skip_file
    )


if __name__ == "__main__":
    main()
