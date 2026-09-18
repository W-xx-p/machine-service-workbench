from __future__ import annotations

from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import hash_password
from app.database import SessionLocal
from app.models import (
    Alarm,
    KnowledgeItem,
    MachineModel,
    MaintenanceCase,
    Part,
    ProductSeries,
    User,
)
from app.services.graph import graph_service


VMC_SERIES_URL = "https://haitianprecision.com/cn/products/vertical-2/vertical/"
VMC_CATALOG_URL = "https://haitianprecision.com/wp-content/uploads/2020/06/VMC_GU_2020.5.pdf"
VMC1000_URL = "https://eu.haitianprecision.com/cn/产品/立式加工中心/vmc-ii/vmc1000ii/"
VMC1200_URL = "https://eu.haitianprecision.com/products/vertical-machining-center/vmcll/vmc1200ii/"
V8H_URL = "https://eu.haitianprecision.com/products/vertical-machining-center/v-series/v8h/"

SERIES = [
    {
        "code": "VMC-II",
        "name": "VMC II 立式加工中心系列",
        "description": "公开产品页显示，该系列面向通用机械、汽车、民用航空、仪表、纺织机械等行业中小型零件的高速精密加工。",
        "manufacturer": "海天精工",
        "source_url": VMC_SERIES_URL,
        "source_title": "海天精工 VMC II 系列产品页",
        "data_classification": "official_public",
    },
    {
        "code": "V-HIGH-SPEED",
        "name": "V 系列高速立式加工中心",
        "description": "基于 VMC II 开发的高速立式加工中心公开产品系列样本。",
        "manufacturer": "海天精工",
        "source_url": V8H_URL,
        "source_title": "海天精工 V8H 产品页",
        "data_classification": "official_public",
    },
]

MODELS = [
    {
        "series_code": "VMC-II",
        "code": "VMC600II",
        "name": "VMC600II 立式加工中心",
        "specs": {"catalog_note": "官方系列目录列出的型号；详细参数待企业受控资料补充"},
        "source_url": VMC_SERIES_URL,
        "source_title": "海天精工 VMC II 系列产品页",
    },
    {
        "series_code": "VMC-II",
        "code": "VMC850II",
        "name": "VMC850II 立式加工中心",
        "specs": {"catalog_note": "官方系列目录列出的型号；详细参数待企业受控资料补充"},
        "source_url": VMC_SERIES_URL,
        "source_title": "海天精工 VMC II 系列产品页",
    },
    {
        "series_code": "VMC-II",
        "code": "VMC1000II",
        "name": "VMC1000II 立式加工中心",
        "specs": {
            "work_range_xyz_mm": "1000/600/600",
            "rapid_traverse_xyz_m_min": "36/36/36",
            "spindle_speed_rpm": "12000",
            "spindle_power_kw": "11/15",
            "spindle_torque_nm": "52.5/95.5",
        },
        "source_url": VMC1000_URL,
        "source_title": "海天精工 VMC1000II 产品页",
    },
    {
        "series_code": "VMC-II",
        "code": "VMC1200II",
        "name": "VMC1200II 立式加工中心",
        "specs": {
            "work_range_xyz_mm": "1200/600/600",
            "rapid_traverse_xyz_m_min": "36/36/36",
            "spindle_speed_rpm": "12000",
            "spindle_power_kw": "11/15",
            "spindle_torque_nm": "52.5/95.5",
        },
        "source_url": VMC1200_URL,
        "source_title": "海天精工 VMC1200II 产品页",
    },
    {
        "series_code": "VMC-II",
        "code": "VMC1300II",
        "name": "VMC1300II 立式加工中心",
        "specs": {"catalog_note": "官方系列目录列出的型号；详细参数待企业受控资料补充"},
        "source_url": VMC_SERIES_URL,
        "source_title": "海天精工 VMC II 系列产品页",
    },
    {
        "series_code": "V-HIGH-SPEED",
        "code": "V8H",
        "name": "V8H 高速立式加工中心",
        "specs": {
            "work_range_xyz_mm": "850/500/600",
            "rapid_traverse_xyz_m_min": "48/48/48",
            "spindle_speed_rpm": "12000 或 15000",
            "spindle_power_kw": "11/18.5",
            "spindle_torque_nm": "62/86",
        },
        "source_url": V8H_URL,
        "source_title": "海天精工 V8H 产品页",
    },
]

DEMO_MODELS = ["VMC600II", "VMC850II", "VMC1000II", "VMC1200II", "VMC1300II"]

ALARMS = [
    {
        "code": "ATC-1001",
        "title": "演示：换刀气路压力不足",
        "severity": "high",
        "system": "刀库与气动系统",
        "applies_to": DEMO_MODELS,
        "symptoms": ["自动换刀中止", "刀库动作迟缓", "气压状态未满足"],
        "possible_causes": ["外部气源压力不足", "储气罐或气路泄漏", "过滤减压组件异常", "压力开关状态异常"],
        "checks": [
            "停止自动循环并记录报警发生步骤",
            "由授权人员核对机床铭牌、控制系统版本和气源压力显示",
            "在能源隔离后检查可见气路、接头及储气罐是否泄漏",
            "核对压力开关输入状态，不跨接安全信号",
        ],
        "actions": ["恢复符合企业受控手册要求的供气条件", "若输入状态异常，按电气图由授权人员排查"],
        "stop_conditions": ["刀具或刀臂位置不明", "存在人员进入危险区的可能", "需要绕过门锁或安全互锁"],
        "source_title": "演示知识：根据公开产品特性构造的流程样例",
        "source_url": VMC_SERIES_URL,
        "source_section": "换刀稳定性（仅说明产品特性，不是维修指令）",
    },
    {
        "code": "SP-2001",
        "title": "演示：主轴温升异常",
        "severity": "high",
        "system": "主轴系统",
        "applies_to": ["VMC1000II", "VMC1200II", "V8H"],
        "symptoms": ["主轴温度趋势异常", "连续加工后停机", "加工精度波动"],
        "possible_causes": ["冷却回路流量不足", "过滤器堵塞", "冷却液状态异常", "温度传感器或接线异常"],
        "checks": [
            "立即停止高负载加工并保留温度趋势与负载记录",
            "核对机型、主轴配置和受控手册规定的温度边界",
            "由授权人员检查冷却机状态、液位、过滤器和可见泄漏",
        ],
        "actions": ["排除冷却回路问题后空载验证", "温度持续异常时联系制造商服务人员"],
        "stop_conditions": ["出现异响、焦味、烟雾或明显振动", "温度超过企业受控手册停机值"],
        "source_title": "演示知识：根据公开产品特性构造的流程样例",
        "source_url": VMC1000_URL,
        "source_section": "高速、高性能主轴（仅说明产品特性，不是维修指令）",
    },
    {
        "code": "CP-3001",
        "title": "演示：排屑或冲屑效果下降",
        "severity": "medium",
        "system": "冷却与排屑系统",
        "applies_to": ["VMC1000II", "VMC1200II", "V8H"],
        "symptoms": ["切屑堆积", "冲屑覆盖不足", "加工区积液"],
        "possible_causes": ["喷嘴方向偏移", "过滤组件堵塞", "泵流量下降", "排屑通道阻塞"],
        "checks": ["停止加工并执行能源隔离", "检查可见喷嘴、过滤组件和排屑通道", "确认切屑类型与当前排屑配置匹配"],
        "actions": ["按企业受控保养规程清理过滤与排屑通道", "恢复后进行短时低风险验证"],
        "stop_conditions": ["需要进入运动部件区域", "存在高温切屑、尖锐切屑或冷却液喷射风险"],
        "source_title": "演示知识：根据公开产品特性构造的流程样例",
        "source_url": V8H_URL,
        "source_section": "一体式底盘排屑（仅说明产品特性，不是维修指令）",
    },
]

PARTS = [
    {
        "part_no": "DEMO-AIR-FILTER-01",
        "name": "演示气路过滤元件",
        "category": "气动系统",
        "applies_to": DEMO_MODELS,
        "replaces": [],
        "key_specs": {"ordering_status": "禁止按演示编号采购"},
        "verification_notes": ["必须按机床序列号、气动原理图和原件铭牌三方核对", "由企业备件主数据审核后才可下单"],
        "source_title": "演示备件主数据",
        "source_url": None,
    },
    {
        "part_no": "DEMO-SP-COOL-FILTER-01",
        "name": "演示主轴冷却过滤元件",
        "category": "主轴冷却",
        "applies_to": ["VMC1000II", "VMC1200II", "V8H"],
        "replaces": [],
        "key_specs": {"ordering_status": "禁止按演示编号采购"},
        "verification_notes": ["核对冷却机型号、接口尺寸和过滤精度", "不得仅凭相似外观替代"],
        "source_title": "演示备件主数据",
        "source_url": None,
    },
]

CASES = [
    {
        "case_no": "DEMO-CASE-2026-001",
        "title": "演示案例：换刀过程中气压条件不满足",
        "model_code": "VMC1000II",
        "alarm_code": "ATC-1001",
        "symptom": "自动换刀在准备阶段中止，重新启动后偶发复现。",
        "root_cause": "演示结论：外部供气波动叠加接头轻微泄漏。",
        "resolution": "演示流程：能源隔离后处理泄漏点，并由授权人员恢复受控供气条件。",
        "verification": "演示验证：空载换刀循环、报警记录和气压趋势均正常后，由工程师签字关闭。",
        "risk_level": "high",
    },
    {
        "case_no": "DEMO-CASE-2026-002",
        "title": "演示案例：连续加工后主轴温度趋势上升",
        "model_code": "V8H",
        "alarm_code": "SP-2001",
        "symptom": "高转速连续加工后温度趋势高于同类历史批次。",
        "root_cause": "演示结论：冷却过滤元件维护超期导致流量下降。",
        "resolution": "演示流程：根据受控保养规程处理过滤组件，并检查冷却液状态。",
        "verification": "演示验证：按批准的空载和试件方案复核温度趋势与加工结果。",
        "risk_level": "high",
    },
]

# One deliberately narrow graph path is included in the first release. The
# model-to-subsystem edge is backed by the manufacturer's public catalogue;
# fault, part and case edges remain explicitly labelled as demo process data.
SUBSYSTEMS = [
    {
        "code": "ATC",
        "name": "机械手式刀库与换刀系统",
        "model_codes": ["VMC850II", "VMC1000II", "VMC1200II"],
        "source_title": "海天精工立式加工中心公开产品目录",
        "source_url": VMC_CATALOG_URL,
        "source_section": "VMC II 刀库：24 刀机械手刀库",
        "data_classification": "official_public",
    }
]

FAULT_PATHS = [
    {
        "alarm_code": "ATC-1001",
        "subsystem_code": "ATC",
        "part_nos": ["DEMO-AIR-FILTER-01"],
        "source_title": "演示故障关联：待企业受控资料复核",
        "source_url": None,
        "source_section": "换刀气路压力关联样例",
        "data_classification": "demo_process_data",
    }
]


def seed_database(include_demo: bool | None = None) -> None:
    settings = get_settings()
    if include_demo is None:
        include_demo = settings.seed_demo_data
    with SessionLocal() as db:
        admin = db.scalar(select(User).where(User.username == settings.admin_username))
        if not admin:
            db.add(
                User(
                    username=settings.admin_username,
                    display_name="系统管理员",
                    password_hash=hash_password(settings.admin_password),
                    role="admin",
                    active=True,
                )
            )

        if not include_demo:
            db.commit()
            return

        series_by_code: dict[str, ProductSeries] = {}
        for item in SERIES:
            row = db.scalar(select(ProductSeries).where(ProductSeries.code == item["code"]))
            if not row:
                row = ProductSeries(**item)
                db.add(row)
                db.flush()
            series_by_code[item["code"]] = row

        for item in MODELS:
            if db.scalar(select(MachineModel).where(MachineModel.code == item["code"])):
                continue
            payload = {key: value for key, value in item.items() if key != "series_code"}
            db.add(
                MachineModel(
                    **payload,
                    series_id=series_by_code[item["series_code"]].id,
                    model_version="public-web-2026-09",
                    data_classification="official_public",
                )
            )

        for item in ALARMS:
            if not db.scalar(select(Alarm).where(Alarm.code == item["code"])):
                db.add(Alarm(**item, data_classification="demo_process_data", review_status="published"))
        for item in PARTS:
            if not db.scalar(select(Part).where(Part.part_no == item["part_no"])):
                db.add(Part(**item, data_classification="demo_process_data", review_status="published"))
        for item in CASES:
            if not db.scalar(select(MaintenanceCase).where(MaintenanceCase.case_no == item["case_no"])):
                db.add(
                    MaintenanceCase(
                        **item, data_classification="demo_process_data", review_status="published"
                    )
                )
        if not db.scalar(select(KnowledgeItem).where(KnowledgeItem.title == "VMC II 系列公开产品特性")):
            db.add(
                KnowledgeItem(
                    title="VMC II 系列公开产品特性",
                    item_type="product_fact",
                    content="公开产品页说明该系列采用高刚性主机框架、全封顶防护，并配置与换刀稳定性相关的储气罐。",
                    applies_to=DEMO_MODELS,
                    source_title="海天精工 VMC II 系列产品页",
                    source_url=VMC_SERIES_URL,
                    source_section="亮点",
                    version="public-web-2026-09",
                    confidence=0.98,
                    review_status="published",
                    data_classification="official_public",
                )
            )
        db.commit()

    catalog_payload = [
        {
            **item,
            "series_name": next(s["name"] for s in SERIES if s["code"] == item["series_code"]),
            "manufacturer": "海天精工",
        }
        for item in MODELS
    ]
    graph_service.sync_catalog(catalog_payload)
    graph_service.sync_knowledge(
        [{**item, "data_classification": "demo_process_data"} for item in ALARMS],
        [{**item, "data_classification": "demo_process_data"} for item in PARTS],
        [{**item, "data_classification": "demo_process_data"} for item in CASES],
    )
    graph_service.sync_fault_paths(SUBSYSTEMS, FAULT_PATHS)


if __name__ == "__main__":
    from app.database import init_db

    init_db()
    seed_database()
