from __future__ import annotations
from typing import List, Optional, Dict, Any
import sys
import json
from abc import ABC, abstractmethod 
from enum import Enum 

# -------------------------------------------------------------------------
# 1. 異常、常量與枚舉定義
# -------------------------------------------------------------------------
class SafetyViolationException(Exception):
    pass

class SimulationException(Exception):
    """模擬過程中的異常（如功率不足導致模塊失效）"""
    pass

# 模塊規格（新增熱量、HP等模擬參數）
MODULE_SPECS = {
    "Frame": {"mass": 1000, "total_slots": 10},
    "Reactor": {
        "Fusion": {"slot_cost": 3, "mass": 300, "power_output": 1000, "heat_generation": 20, "power_draw": 50},  # 冷却系统功率需求
        "Antimatter": {"slot_cost": 3, "mass": 450, "power_output": 1000, "heat_generation": 30, "power_draw": 70}
    },
    "Engine": {
        "Ion": {"slot_cost": 2, "mass": 100, "power_draw": 250, "thrust": 500, "heat_generation": 15},
        "Plasma": {"slot_cost": 2, "mass": 120, "power_draw": 250, "thrust": 750, "heat_generation": 25}
    },
    "LifeSupport": {
        "Standard": {"slot_cost": 2, "mass": 80, "power_draw": 50, "heat_generation": 5},
        "Advanced": {"slot_cost": 2, "mass": 70, "power_draw": 50, "heat_generation": 8}
    },
    "Bridge": {
        "Explorer": {"slot_cost": 1, "mass": 50, "power_draw": 75, "heat_generation": 3},
        "Command": {"slot_cost": 1, "mass": 60, "power_draw": 75, "heat_generation": 4}
    },
    "Shield": {
        "Magnetic": {"slot_cost": 1, "mass": 40, "power_draw": 100, "heat_generation": 10, "max_hp": 100},
        "Phase": {"slot_cost": 1, "mass": 40, "power_draw": 100, "heat_generation": 12, "max_hp": 120}
    },
    "Sensors": {
        "Basic": {"slot_cost": 1, "mass": 30, "power_draw": 50, "heat_generation": 2},
        "Advanced": {"slot_cost": 1, "mass": 35, "power_draw": 50, "heat_generation": 3}
    }
}

# 構建階段枚舉（保持不變）
class BuildPhase:
    INIT = "INIT"
    FRAME_SET = "FRAME_SET"
    CORE_LOCKED = "CORE_LOCKED"
    FINALIZED = "FINALIZED"

# 外部事件枚舉
class ExternalEvent(Enum):
    SHIELD_HIT = "ShieldHit"
    ENGINE_FULL_THRUST = "EngineFullThrust"

# 模塊運行狀態
class ModuleState(Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"
    FAILED = "FAILED"
    UNAVAILABLE = "UNAVAILABLE"
    INACTIVE = "INACTIVE"
    EMERGENCY = "EMERGENCY"
    OFFLINE_POWER_DENIED = "OFFLINE_POWER_DENIED"

# 功率優先級 (P1最高)
POWER_PRIORITY = [
    "LifeSupport",  # P1：生命支持
    "Reactor",      # P2：反應堆冷卻系統
    "Bridge",       # P3：控制中樞
    "Engine",       # P4：推進系統
    "Shield",       # P5：防護系統
    "Sensors"       # P6：探測系統
]

# -------------------------------------------------------------------------
# 2. 測試介面 (TASK TESTING - Dependency Injection)
# -------------------------------------------------------------------------

class ILogger(ABC):
    """概念介面: void log(String message)"""
    @abstractmethod
    def log(self, message: str):
        pass

class IAlertSystem(ABC):
    """概念介面: void alert(String message)"""
    @abstractmethod
    def alert(self, message: str):
        pass

# -------------------------------------------------------------------------
# 3. 模塊類（管理動態狀態）
# -------------------------------------------------------------------------
class Module:
    def __init__(self, category: str, spec: dict):
        self.category = category
        self.spec = spec
        # 初始化狀態：Reactor默認ONLINE，其他模塊OFFLINE
        self.state = ModuleState.ONLINE if category == "Reactor" else ModuleState.OFFLINE
        self.current_power = 0
        self.heat = 0
        self.hp = spec.get("max_hp", 100)
        self.is_full_thrust = False  # 僅Engine使用

    def update_power(self, allocated_power: int, logger: ILogger) -> None:
        """更新模塊獲得的功率，調整運行狀態"""
        self.current_power = allocated_power
        required = self.spec.get("power_draw", 0)
        
        if self.state == ModuleState.FAILED:
            # 失效後，無法恢復
            self.current_power = 0
            return

        if self.category == "Reactor":
            # Reactor: 功率分配給冷卻系統。若分配足夠，則狀態 ONLINE（提供輸出）；否則 FAILED。
            if allocated_power >= required:
                self.state = ModuleState.ONLINE
            elif allocated_power > 0:
                self.state = ModuleState.DEGRADED
                logger.log(f"Reactor Cooling is DEGRADED. Allocated: {allocated_power}W / Required: {required}W")
            else:
                self.state = ModuleState.FAILED # 冷卻系統斷電，反應堆立即失效 (P2優先級的關鍵)
                logger.log("Reactor Cooling Failed: Power denied. Reactor status now FAILED.")
        
        elif allocated_power >= required:
            self.state = ModuleState.ONLINE
        elif allocated_power > 0 and allocated_power < required:
            self.state = ModuleState.DEGRADED
            logger.log(f"{self.category} ({self.spec['type']}) power is degraded. Allocated: {allocated_power}W / Required: {required}W")
        else:  # allocated_power == 0
            self.state = ModuleState.OFFLINE
            if self.category == "Engine" and self.is_full_thrust:
                 # 引擎在被要求全推力時斷電，狀態變為 OFFLINE_POWER_DENIED
                 self.state = ModuleState.OFFLINE_POWER_DENIED 

    def generate_heat(self, logger: ILogger) -> None:
        """根據運行狀態生成熱量"""
        if self.state in [ModuleState.ONLINE, ModuleState.DEGRADED]:
            base_heat = self.spec.get("heat_generation", 0)
            
            # 引擎滿推力時熱量翻倍
            if self.category == "Engine" and self.is_full_thrust:
                 base_heat *= 2
                 logger.log(f"Engine ({self.spec['type']}) operating at full thrust. Heat doubled to {base_heat}")
            
            self.heat += base_heat

    def dissipate_heat(self) -> None:
        """熱量自然消散（每次tick消散10%）"""
        self.heat = max(0, int(self.heat * 0.9))

    def check_overheat(self, alerter: IAlertSystem) -> None:
        """檢查是否過熱，觸發失效"""
        OVERHEAT_THRESHOLD = 100 # 過熱閾值
        if self.heat > OVERHEAT_THRESHOLD:
            self.state = ModuleState.FAILED
            self.heat = OVERHEAT_THRESHOLD
            alerter.alert(f"{self.category} ({self.spec['type']}) Overheated and Failed! Current heat: {self.heat}")

    def take_damage(self, damage: int = 20) -> None:
        """Shield 受擊，減少 HP"""
        if self.category == "Shield" and self.state != ModuleState.FAILED:
            self.hp = max(0, self.hp - damage)
            if self.hp == 0:
                self.state = ModuleState.FAILED

# -------------------------------------------------------------------------
# 4. DSL 核心類 (保持原功能，finalize 時返回帶動態模塊的藍圖)
# -------------------------------------------------------------------------
class BlueprintBuilder:
    def __init__(self):
        self.phase = BuildPhase.INIT
        self.frame = None
        self.reactors = []
        self.engine = None
        self.life_support = None
        self.bridge = None
        self.shield = None
        self.sensors = None
        self.slots_used = 0

    def _get_spec(self, module_category, module_type):
        category_specs = MODULE_SPECS.get(module_category)
        if not category_specs or module_type not in category_specs:
            raise SafetyViolationException(f"Unknown module type: {module_category} - {module_type}")
        spec = category_specs[module_type].copy()
        spec['type'] = module_type
        return spec

    def _check_slots(self, cost):
        if not self.frame:
            raise SafetyViolationException("Frame not set. Cannot check slots.")
        remaining = self.frame['total_slots'] - self.slots_used
        if cost > remaining:
            raise SafetyViolationException(f"[B-307] Slot limitation exceeded. Required: {cost}, Available: {remaining}")

    def _check_phase(self, allowed_phases, rule_id):
        if self.phase not in allowed_phases:
            raise SafetyViolationException(
                f"[{rule_id}] Operation not allowed in phase '{self.phase}'. Allowed phases: {allowed_phases}"
            )

    def _check_not_finalized(self):
        if self.phase == BuildPhase.FINALIZED:
            raise SafetyViolationException("[A-212] Finalized Blueprints Cannot Be Modified.")

    def set_frame(self):
        if self.phase != BuildPhase.INIT:
            raise SafetyViolationException("[A-103] Frame must be set immediately after start_blueprint.")
        self.frame = MODULE_SPECS['Frame']
        self.phase = BuildPhase.FRAME_SET
        return self

    def add_reactor(self, type_name):
        self._check_not_finalized()
        self._check_phase([BuildPhase.FRAME_SET], "A-305")
        spec = self._get_spec("Reactor", type_name)
        self._check_slots(spec['slot_cost'])
        self.reactors.append(spec)
        self.slots_used += spec['slot_cost']
        return self

    def add_engine(self, type_name):
        self._check_not_finalized()
        self._check_phase([BuildPhase.FRAME_SET], "A-305")
        if self.engine:
            raise SafetyViolationException("Only one Engine allows.")
        spec = self._get_spec("Engine", type_name)
        self._check_slots(spec['slot_cost'])
        self.engine = spec
        self.slots_used += spec['slot_cost']
        return self

    def add_life_support(self, type_name):
        self._check_not_finalized()
        self._check_phase([BuildPhase.FRAME_SET], "A-305")
        if self.life_support:
            raise SafetyViolationException("Only one LifeSupport system allowed.")
        spec = self._get_spec("LifeSupport", type_name)
        self._check_slots(spec['slot_cost'])
        self.life_support = spec
        self.slots_used += spec['slot_cost']
        return self

    def add_bridge(self, type_name):
        self._check_not_finalized()
        self._check_phase([BuildPhase.FRAME_SET], "A-305")
        if self.bridge:
            raise SafetyViolationException("Only one Bridge allowed.")
        spec = self._get_spec("Bridge", type_name)
        self._check_slots(spec['slot_cost'])
        self.bridge = spec
        self.slots_used += spec['slot_cost']
        return self

    def lock_core_systems(self):
        self._check_not_finalized()
        self._check_phase([BuildPhase.FRAME_SET], "A-305")
        if not (self.reactors and self.engine and self.life_support and self.bridge):
            raise SafetyViolationException("[B-209] Core System Integrity violated: Missing core modules.")
        self.phase = BuildPhase.CORE_LOCKED
        return self

    def add_shield(self, type_name):
        self._check_not_finalized()
        self._check_phase([BuildPhase.CORE_LOCKED], "A-305")
        if self.shield:
            raise SafetyViolationException("Only one Shield allowed.")
        spec = self._get_spec("Shield", type_name)
        has_fusion = any(r['type'] == "Fusion" for r in self.reactors)
        has_antimatter = any(r['type'] == "Antimatter" for r in self.reactors)
        if has_fusion and type_name == "Phase":
            raise SafetyViolationException("[B-440] Cannot install Phase Shield with Fusion Reactor.")
        if has_antimatter and type_name == "Magnetic":
            raise SafetyViolationException("[B-440] Cannot install Magnetic Shield with Antimatter Reactor.")
        self._check_slots(spec['slot_cost'])
        self.shield = spec
        self.slots_used += spec['slot_cost']
        return self

    def add_sensors(self, type_name):
        self._check_not_finalized()
        self._check_phase([BuildPhase.CORE_LOCKED], "A-305")
        if self.sensors:
            raise SafetyViolationException("Only one Sensors module allowed.")
        spec = self._get_spec("Sensors", type_name)
        self._check_slots(spec['slot_cost'])
        self.sensors = spec
        self.slots_used += spec['slot_cost']
        return self

    def finalize_blueprint(self):
        self._check_not_finalized()
        if self.phase != BuildPhase.CORE_LOCKED:
            if self.phase == BuildPhase.FRAME_SET:
                 raise SafetyViolationException("Must lock core systems before finalizing.")
            raise SafetyViolationException("Blueprint must be in CORE_LOCKED phase to finalize.")
        
        # 構建動態模塊實例（關鍵修改：從靜態規格轉為動態模塊）
        modules_map = {
            "Reactor": self.reactors,
            "Engine": [self.engine] if self.engine else [],
            "LifeSupport": [self.life_support] if self.life_support else [],
            "Bridge": [self.bridge] if self.bridge else [],
            "Shield": [self.shield] if self.shield else [],
            "Sensors": [self.sensors] if self.sensors else []
        }
        
        # 將規格轉換為 Module 實例
        dynamic_modules = {}
        for category, specs_list in modules_map.items():
            if specs_list:
                # 使用 Module 類初始化動態實例
                dynamic_modules[category] = [Module(category, spec) for spec in specs_list if spec]

        self.phase = BuildPhase.FINALIZED
        return SimFinalizedBlueprint(
            specs=self._calculate_specs(),
            modules=dynamic_modules
        )

    def _calculate_specs(self):
        total_mass = self.frame['mass']
        modules = self.reactors + [self.engine, self.life_support, self.bridge, self.shield, self.sensors]
        active_modules = [m for m in modules if m]
        total_mass += sum(m['mass'] for m in active_modules)
        total_power_output = sum(r['power_output'] for r in self.reactors)
        total_power_draw = sum(m.get('power_draw', 0) for m in active_modules)
        total_thrust = self.engine['thrust'] if self.engine else 0
        return {
            "total_slots": self.frame['total_slots'],
            "slots_used": self.slots_used,
            "total_mass": total_mass,
            "total_power_output": total_power_output,
            "total_power_consumption": total_power_draw,
            "power_balance": total_power_output - total_power_draw,
            "thrust_to_weight_ratio": total_thrust / total_mass if total_mass > 0 else 0
        }

# -------------------------------------------------------------------------
# 5. 藍圖規格與帶模擬功能的定稿藍圖
# -------------------------------------------------------------------------
class SimFinalizedBlueprint:
    def __init__(self, specs: dict, modules: Dict[str, List[Module]]):
        self.specs = specs
        self.modules = modules  # 動態模塊實例
        self.total_power_output = specs['total_power_output']
        # 记录已安装的模块
        self.installed_modules = {category: len(modules_list) > 0 for category, modules_list in modules.items()}

    def print_spec(self):
        """Task 2: Visualization"""
        s = self.specs
        print("+" + "="*48 + "+")
        print(f"| {'SPACESHIP BLUEPRINT SPECIFICATION':^46} |")
        print("+" + "="*48 + "+")
        print(f"| {'Total Slots':<30} | {s['total_slots']:>13} |")
        print(f"| {'Slots Used':<30} | {s['slots_used']:>13} |")
        print("|" + "-"*48 + "|")
        print(f"| {'Total Mass':<30} | {s['total_mass']:>10} kg |")
        print("|" + "-"*48 + "|")
        print(f"| {'Total Power Output':<30} | {s['total_power_output']:>11} W |")
        print(f"| {'Total Power Consumption':<30} | {s['total_power_consumption']:>11} W |")
        print(f"| {'Power Balance':<30} | {s['power_balance']:>11} W |")
        print("|" + "-"*48 + "|")
        print(f"| {'Thrust-to-Weight Ratio':<30} | {s['thrust_to_weight_ratio']:>13.4f} |")
        print("+" + "="*48 + "+")

# -------------------------------------------------------------------------
# 6. 太空船模擬器（ShipSimulator - Task 1: Simulator）
# -------------------------------------------------------------------------
class ShipSimulator:
    def __init__(self, blueprint: SimFinalizedBlueprint, logger: ILogger, alerter: IAlertSystem):
        self.logger = logger
        self.alerter = alerter
        self.blueprint = blueprint
        self.modules = blueprint.modules
        self.current_tick = 0
        self.full_thrust_enabled = False

        # 初始化模塊狀態驗證
        self.logger.log(f"Simulator initialized. Initial Power Output: {self.blueprint.total_power_output}W")
        self.logger.log(f"Installed modules: {[cat for cat, installed in self.blueprint.installed_modules.items() if installed]}")
        
    def _get_module_status_string(self, module: Optional[Module], category: str) -> str:
        """根據模塊狀態返回 JSON 要求的狀態字串"""
        if not module or not self.blueprint.installed_modules.get(category, False):
            return "UNAVAILABLE"
        
        # 處理特殊狀態
        if module.state == ModuleState.FAILED:
            return "FAILED"
        if module.state == ModuleState.OFFLINE and category == "Engine" and module.is_full_thrust:
            return "OFFLINE_POWER_DENIED" 
        if module.state == ModuleState.DEGRADED:
            return "DEGRADED"

        # 處理默認狀態
        if module.state == ModuleState.ONLINE:
            return "ONLINE"
        # 其他情況（包括未啟動、被斷電）
        return "OFFLINE"

    def _get_json_state(self) -> Dict[str, Any]:
        """生成符合測試要求 JSON 格式的當前狀態"""
        
        # 1. 聚合計算
        # 修正：total_power_draw 應為模組實際獲得的功率總和
        total_power_draw = sum(m.current_power for category in self.modules for m in self.modules[category])
        total_heat = sum(m.heat for category in self.modules for m in self.modules[category])
        
        # 檢查冷卻系統狀態 (Reactor)
        cooler_status = "INACTIVE"
        if "Reactor" in self.modules:
            reactor_module = self.modules["Reactor"][0]
            if reactor_module.state in [ModuleState.ONLINE, ModuleState.DEGRADED]:
                 cooler_status = "ACTIVE"
            elif reactor_module.state == ModuleState.FAILED:
                 cooler_status = "FAILED"
        
        state_data = {
            "total_power_draw": total_power_draw,
            "total_power_output": self.blueprint.total_power_output,
            "heat": total_heat,
            "cooler_status": cooler_status,
        }
        
        # 2. 模塊狀態
        
        # LifeSupport, Engine, Bridge 必須存在 (B-209 規則確保)
        state_data["life_support_status"] = self._get_module_status_string(self.modules["LifeSupport"][0], "LifeSupport")
        state_data["engine_status"] = self._get_module_status_string(self.modules["Engine"][0], "Engine")
        state_data["bridge_status"] = self._get_module_status_string(self.modules["Bridge"][0], "Bridge")
        
        # Shield & Sensors
        state_data["shield_status"] = self._get_module_status_string(
            self.modules.get("Shield", [None])[0], "Shield"
        )
        state_data["sensors_status"] = self._get_module_status_string(
            self.modules.get("Sensors", [None])[0], "Sensors"
        )
        
        return state_data

    def _allocate_power(self) -> None:
        """[動態電源管理] 按優先級分配功率"""
        remaining_power = self.blueprint.total_power_output
        self.logger.log(f"Power allocation started. Available power: {remaining_power}W")

        # P1-P6 分配邏輯
        for category in POWER_PRIORITY:
            if category not in self.modules:
                self.logger.log(f"Skip {category}: Not installed")
                continue
            
            for module in self.modules[category]:
                if module.state == ModuleState.FAILED:
                    module.update_power(0, self.logger)
                    self.logger.log(f"{category} ({module.spec['type']}) is failed. Allocated 0W")
                    continue

                required = module.spec.get("power_draw", 0)
                
                # Reactor (P2) 需要電力來運行冷卻系統
                if category == "Reactor":
                    allocated = min(required, remaining_power)
                else:
                    allocated = min(required, remaining_power)
                
                module.update_power(allocated, self.logger)
                remaining_power -= allocated
                
                if allocated < required:
                    self.logger.log(f"Power shortage: {category} allocated only {allocated}W / {required}W. Remaining: {remaining_power}W")
                elif category != "Reactor": # Reactor 不會減少總輸出，除非冷卻失敗
                    self.logger.log(f"{category} ({module.spec['type']}): Allocated {allocated}W. Remaining: {remaining_power}W")


    def _process_events(self, events: List[ExternalEvent]) -> None:
        """處理外部事件"""
        for event in events:
            if event == ExternalEvent.ENGINE_FULL_THRUST:
                self.full_thrust_enabled = True
                if "Engine" in self.modules:
                    engine = self.modules["Engine"][0]
                    engine.is_full_thrust = True
                    self.logger.log("Event processed: Engine Full Thrust initiated")
                else:
                    self.alerter.alert("Event: EngineFullThrust - No engine installed")
            elif event == ExternalEvent.SHIELD_HIT:
                if "Shield" in self.modules:
                    shield = self.modules["Shield"][0]
                    if shield.state != ModuleState.FAILED:
                        shield.take_damage()
                        self.alerter.alert(f"Event: ShieldHit - HP remaining: {shield.hp}")
                        if shield.hp == 0:
                            self.alerter.alert("Critical: Shield failed after hit!")
                    else:
                        self.alerter.alert("Event: ShieldHit - Shield is already failed")
                else:
                    self.alerter.alert("Event: ShieldHit - No shield installed")

    def _update_thermodynamics(self) -> None:
        """[熱力學] 生成熱量、消散、檢查過熱"""
        self.logger.log("Thermodynamics update started")
        for category in self.modules:
            for module in self.modules[category]:
                module.generate_heat(self.logger)
                module.dissipate_heat()
                module.check_overheat(self.alerter)
                self.logger.log(f"{category} ({module.spec['type']}): Heat={module.heat}, State={module.state.value}")

    def _handle_chain_reactions(self) -> None:
        """系統連鎖反應"""
        # 1. 反應堆失效 → 全船斷電告警
        if "Reactor" in self.modules and self.modules["Reactor"][0].state == ModuleState.FAILED:
            self.alerter.alert("Chain Reaction: Reactor failed - All systems may lose power!")
        # 2. 生命支持異常 → 船員危險
        if "LifeSupport" in self.modules:
            ls = self.modules["LifeSupport"][0]
            if ls.state in [ModuleState.DEGRADED, ModuleState.OFFLINE, ModuleState.FAILED]:
                self.alerter.alert(f"Chain Reaction: Life Support Critical! Status: {ls.state.value}")
        # 3. 護盾失效 → 橋接系統告警
        if "Shield" in self.modules and self.modules["Shield"][0].state == ModuleState.FAILED and "Bridge" in self.modules:
            self.alerter.alert("Chain Reaction: Shield failed - Bridge initiating emergency protocols")

    def tick(self, events_json: str) -> None:
        """
        離散時間驅動函數：每次呼叫代表 1 個時間單位
        :param events_json: 外部事件列表的JSON字符串
        """
        try:
            # 解析事件JSON
            event_names = json.loads(events_json) if events_json.strip() else []
            events = [ExternalEvent(name) for name in event_names]
        except json.JSONDecodeError:
            self.alerter.alert("Invalid JSON format for events")
            events = []
        except ValueError as e:
            self.alerter.alert(f"Unknown event type: {str(e)}")
            events = []

        self.current_tick += 1
        self.logger.log(f"\n=== Tick {self.current_tick} Started ===")

        # 1. 處理外部事件
        self._process_events(events)

        # 2. 功率分配
        self._allocate_power()

        # 3. 熱力學更新
        self._update_thermodynamics()

        # 4. 鏈式反應
        self._handle_chain_reactions()

        # 5. 重置單 tick 狀態
        if "Engine" in self.modules:
            for engine in self.modules["Engine"]:
                engine.is_full_thrust = False
        self.full_thrust_enabled = False

        self.logger.log(f"=== Tick {self.current_tick} Completed ===\n")

# -------------------------------------------------------------------------
# 7. 測試專用實作 (Task Testing)
# -------------------------------------------------------------------------
class ConsoleLogger(ILogger):
    def log(self, message: str):
        """日志輸出到stderr，避免污染stdout的JSON輸出"""
        print(f"[LOG] {message}", file=sys.stderr)

class ConsoleAlerter(IAlertSystem):
    def alert(self, message: str):
        """告警輸出到stderr"""
        print(f"[ALERT] {message}", file=sys.stderr)

# -------------------------------------------------------------------------
# 8. 模擬器主迴圈 (MAIN SIMULATOR LOOP - Mandatory I/O)
# -------------------------------------------------------------------------
def main_simulator_loop(simulator: ShipSimulator):
    """
    處理 stdin 輸入，根據指令執行 tick 或 print_state
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        
        parts = line.split(' ', 1)
        command = parts[0]
        
        if command == "tick" and len(parts) == 2:
            events_json = parts[1]
            simulator.tick(events_json)
            
        elif command == "print_state":
            state = simulator._get_json_state()
            # 嚴格要求輸出到 stdout
            print(json.dumps(state, indent=None)) 
            
        else:
            simulator.alerter.alert(f"Unknown command: {line}")

# -------------------------------------------------------------------------
# 9. DSL 入口函數 (保持不變)
# -------------------------------------------------------------------------
def start_blueprint() -> BlueprintBuilder:
    return BlueprintBuilder()

# -------------------------------------------------------------------------
# 10. 本地測試執行區
# -------------------------------------------------------------------------
if __name__ == "__main__":
    # 1. 設計並定稿藍圖
    try:
        blueprint = (start_blueprint()
                     .set_frame()
                     .add_reactor("Fusion")
                     .add_engine("Plasma")
                     .add_life_support("Advanced")
                     .add_bridge("Command")
                     .lock_core_systems()
                     .add_shield("Magnetic")
                     .add_sensors("Basic")
                     .finalize_blueprint())
        blueprint.print_spec()
    except SafetyViolationException as e:
        print(f"Blueprint Design Failed: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. 初始化模擬器
    logger_instance = ConsoleLogger()
    alerter_instance = ConsoleAlerter()
    simulator = ShipSimulator(blueprint, logger_instance, alerter_instance)
    
    # 3. 本地測試：模擬輸入命令
    print("\n=== Local Test Simulation ===", file=sys.stderr)
    test_commands = [
        ("print_state", ""),
        ("tick", '["EngineFullThrust"]'),
        ("print_state", ""),
        ("tick", '["ShieldHit", "ShieldHit", "ShieldHit"]'),
        ("print_state", ""),
        ("tick", '["ShieldHit", "ShieldHit"]'),
        ("print_state", "")
    ]

    for cmd, param in test_commands:
        if cmd == "print_state":
            print(f"\n[Test] Executing: {cmd}", file=sys.stderr)
            state = simulator._get_json_state()
            print(json.dumps(state, indent=2))
        elif cmd == "tick":
            print(f"\n[Test] Executing: {cmd} {param}", file=sys.stderr)
            simulator.tick(param)
            