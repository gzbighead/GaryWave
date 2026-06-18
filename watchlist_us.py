# ─── 美股观察清单 ─────────────────────────────────────────────────────────
# 格式: ("代码", "名称")
# 直接加到列表，系统自动分类，无需手动排序

WATCHLIST_US = [
    # 指数
("SPY", "标普500ETF"),
("QQQ", "纳指100ETF-Invesco QQQ Trust"),
("IWB", "罗素1000指数ETF-iShares"),
("IWM", "罗素2000ETF-iShares"),
("GLD", "黄金ETF-SPDR"),
("SLV", "白银ETF-iShares"),
("XLE", "能源指数ETF-SPDR"),
# ─── 美股 ──────────────────────────────────────────────────────────────────
("NVDA", "英伟达"),
("PLTR", "Palantir"),
("TSLA", "特斯拉"),
("MSFT", "微软"),
("AEP", "美国电力"),
("RKLB", "火箭实验室"),
("AAPL", "苹果"),
("AMZN", "亚马逊"),
("MRVL", "迈威尔"),
("CRWD", "CrowdStrike"),
("DDOG", "Datadog"),
("ARM", "ARM Holding"),
("AMD", "美国超微公司"),
("CBRS", "Cerebras Systems"),
("SPCX", "SpaceX"),
# ─── 美加 ETF ──────────────────────────────────────────────────────────────────
("TQQQ", "三倍做多纳指"),
("SOXL", "三倍做多半导体"),
("DBA", "Invesco德银农业ETF"),
("DBC", "商品指数ETF-Invesco"),
("DDM", "2倍做多道指ETF-Proshares"),
("DRN", "三倍做多房地产ETF-Direxion"),
("ERX", "2倍做多能源ETF-Direxion"),
("FAS", "三倍做多金融指数ETF-Direxion"),
("FRI", "First Trust S&P REIT Index Fund"),
("IBB", "生物科技指数ETF-iShares"),
("ICF", "精选美国房地产投资信托基金ETF-iShares"),
("IHE", "iShares安硕美国医药ETF"),
("IJH", "标普中型股指数ETF-iShares"),
("IJR", "标普小盘股指数ETF-iShares"),
("ITA", "iShares安硕美国航空航天与国防ETF"),
("ITB", "美国房屋建筑业ETF-iShares"),
("IVE", "标普500价值指数ETF-iShares"),
("IVV", "标普500ETF-iShares"),
("IVW", "标普500成长股指数ETF-iShares"),
("IWO", "罗素2000成长股指数ETF-iShares"),
("IWV", "罗素3000ETF-iShares"),
("IYC", "iShares安硕美国消费服务ETF"),
("IYF", "金融指数ETF-iShares Dow Jones"),
("IYM", "基础材料ETF-iShares"),
("IYR", "美国房地产指数ETF-iShares"),
("IYT", "运输指数ETF-iShares"),
("IYZ", "美国电信ETF-iShares"),
("KBE", "银行指数ETF-SPDR KBW"),
("KIE", "保险指数ETF-SPDR KBW"),
("MDY", "标普中型股400指数ETF-SPDR"),
("MOO", "农业企业指数ETF-VanEck"),
("NLR", "铀与核能ETF-VanEck"),
("OEF", "标普100指数ETF-iShares"),
("OIH", "石油服务指数ETF-VanEck"),
("PGF", "Invesco优先金融股指数ETF"),
("RTH", "零售指数ETF-VanEck"),
("SMH", "半导体指数ETF-VanEck"),
("SSO", "2倍做多标普500ETF-ProShares"),
("TAN", "太阳能ETF-Invesco"),
("TNA", "三倍做多小盘股ETF-Direxion"),
("TQQQ", "三倍做多纳指ETF-ProShares"),
("TWM", "罗素2000指数ETF-ProShares 两倍做空"),
("UDOW", "三倍做多道指30ETF-ProShares"),
("UNG", "美国天然气ETF"),
("UPRO", "三倍做多标普500ETF-ProShares"),
("URE", "2倍做多房地产ETF-ProShares"),
("UVXY", "1.5倍做多短期期货恐慌指数ETF-Proshares"),
("UWM", "罗素2000指数ETF-ProShares两倍做多"),
("UYG", "两倍做多金融股ETF-ProShares"),
("UYM", "2倍做多基础材料ETF-ProShares"),
("VIXY", "短期期货恐慌指数ETF-Proshares"),
("VNQ", "不动产信托指数ETF-Vanguard"),
("VOO", "标普500ETF-Vanguard"),
("VXX", "标普500短期期货恐慌指数ETN-iPath"),
("VXZ", "恐慌中期做多ETN-iPath S&P"),
("XHB", "标普房屋建筑商ETF-SPDR"),
("XLB", "SPDR原物料类ETF"),
("XLF", "金融行业ETF-SPDR"),
("XLI", "工业指数ETF-SPDR"),
("XLK", "科技行业精选指数ETF-SPDR"),
("XLP", "日常消费品精选行业指数ETF-SPDR"),
("XLU", "公用事业精选行业指数ETF-SPDR"),
("XLV", "医疗保健精选行业指数ETF-SPDR"),
("XLY", "非必需消费类ETF-SPDR"),
("XME", "SPDR标普金属与矿产业ETF"),
("XRT", "标普零售指数ETF-SPDR"),
]

# ─── 指数代码白名单 ────────────────────────────────────────────────────────
INDEX_CODES_US = {"SPY", "QQQ", "IWM", "IWB", "GLD", "SLV", "XLE"}

# ─── ETF板块关键词（顺序敏感，具体词优先于宽泛词）────────────────────────
SECTOR_KEYWORDS_US = {
    "半导体":   ["半导体", "Semiconductor"],
    "科技":     ["科技", "Tech", "技术", "软件", "Software"],
    "人工智能": ["人工智能", "AI"],
    "新能源":   ["太阳能", "Solar", "清洁能源", "铀", "核能"],
    "医疗医药": ["医疗", "医药", "生物科技", "Health", "Biotech", "Pharma"],
    "金融":     ["金融", "银行", "Financial", "Bank"],
    "能源":     ["能源", "石油", "Energy", "Oil"],
    "消费":     ["消费", "Consumer", "零售", "Retail"],
    "工业":     ["工业", "运输", "Industrial", "Transport"],
    "原材料":   ["原材料", "材料", "金属", "矿", "黄金", "白银", "Material", "Metal", "Gold", "Silver", "商品"],
    "房地产":   ["房地产", "Real Estate", "REIT"],
    "国防航天": ["航空", "国防", "Defense", "Aerospace"],
    "公用事业": ["公用", "电信", "Utility", "Telecom"],
    "农业":     ["农业", "Agriculture"],
    "杠杆":     ["倍做多", "倍做空", "三倍", "两倍", "2倍"],
}

def classify_us(symbol, name):
    """返回 (层级, 板块): 层级=index/stock/etf, 板块=ETF时的板块名"""
    if symbol in INDEX_CODES_US:
        return "index", None
    if "ETF" in name.upper():
        for sector, keywords in SECTOR_KEYWORDS_US.items():
            for kw in keywords:
                if kw in name or kw in symbol:
                    return "etf", sector
        return "etf", "其他"
    return "stock", None
