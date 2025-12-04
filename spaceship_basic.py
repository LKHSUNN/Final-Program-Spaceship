import sys

# -------------------------------------------------------------------------
# 1. 異常與常量定義
# -------------------------------------------------------------------------

class SafetyViolationException(Exception):
    """
    自定義異常類，用於在運行時捕獲違反安全規則的設計行為。
    """
    pass

# 所有模組的規格數據 (Module Specifications)
# 使用字典結構便於查找和擴展
MODULE_SPECS = {
    "Frame": {"mass": 1000, "total_slots": 10},
    "Reactor": {
        "Fusion": {"slot_cost": 3, "mass": 300, "power_output": 1000},
        "Antimatter": {"slot_cost": 3, "mass": 450, "power_output": 1000}
    },
    "Engine": {
        "Ion": {"slot_cost": 2, "mass": 100, "power_draw": 250, "thrust": 500},
        "Plasma": {"slot_cost": 2, "mass": 120, "power_draw": 250, "thrust": 750}
    },
    "LifeSupport": {
        "Standard": {"slot_cost": 2, "mass": 80, "power_draw": 50},
        "Advanced": {"slot_cost": 2, "mass": 70, "power_draw": 50}
    },
    "Bridge": {
        "Explorer": {"slot_cost": 1, "mass": 50, "power_draw": 75},
        "Command": {"slot_cost": 1, "mass": 60, "power_draw": 75}
    },
    "Shield": {
        "Magnetic": {"slot_cost": 1, "mass": 40, "power_draw": 100},
        "Phase": {"slot_cost": 1, "mass": 40, "power_draw": 100}
    },
    "Sensors": {
        "Basic": {"slot_cost": 1, "mass": 30, "power_draw": 50},
        "Advanced": {"slot_cost": 1, "mass": 35, "power_draw": 50}
    }
}

# 構建階段枚舉 (Build Phases)
class BuildPhase:
    INIT = "INIT"               # 初始階段
    FRAME_SET = "FRAME_SET"     # 框架已設置，準備安裝核心模組
    CORE_LOCKED = "CORE_LOCKED" # 核心系統已鎖定，準備安裝可選模組
    FINALIZED = "FINALIZED"     # 藍圖已定稿，不可修改

# -------------------------------------------------------------------------
# 2. DSL 核心類 (BlueprintBuilder)
# -------------------------------------------------------------------------

class BlueprintBuilder:
    def __init__(self):
        # 初始狀態為 INIT
        self.phase = BuildPhase.INIT
        
        # 存儲組件數據
        self.frame = None
        self.reactors = []      # 可多個
        self.engine = None      # 只能一個
        self.life_support = None # 只能一個
        self.bridge = None      # 只能一個
        self.shield = None      # 只能一個 (可選)
        self.sensors = None     # 只能一個 (可選)
        
        # 追踪已使用的插槽數
        self.slots_used = 0

    # --- 內部輔助函數 (Helper Functions) ---

    def _get_spec(self, module_category, module_type):
        """根據類別和類型獲取模組規格"""
        category_specs = MODULE_SPECS.get(module_category)
        if not category_specs or module_type not in category_specs:
            raise SafetyViolationException(f"Unknown module type: {module_category} - {module_type}")
        
        # 返回規格副本，並附加類型名稱以便後續檢查 (如 B-440)
        spec = category_specs[module_type].copy()
        spec['type'] = module_type
        return spec

    def _check_slots(self, cost):
        """[B-307] 檢查剩餘插槽是否足夠"""
        if self.frame is None:
            # 雖然正常流程不會發生 (因爲有 Phase 檢查)，但防禦性編程是個好習慣
            raise SafetyViolationException("Frame not set. Cannot check slots.")
            
        remaining = self.frame['total_slots'] - self.slots_used
        if cost > remaining:
            raise SafetyViolationException(f"[B-307] Slot limitation exceeded. Required: {cost}, Available: {remaining}")

    def _check_phase(self, allowed_phases, rule_id):
        """[A-305, A-212] 檢查當前操作是否在允許的階段內"""
        if self.phase not in allowed_phases:
            # 生成錯誤信息，提示當前階段和允許的階段
            raise SafetyViolationException(
                f"[{rule_id}] Operation not allowed in phase '{self.phase}'. "
                f"Allowed phases: {allowed_phases}"
            )

    def _check_not_finalized(self):
        """[A-212] 檢查藍圖是否已定稿"""
        if self.phase == BuildPhase.FINALIZED:
            raise SafetyViolationException("[A-212] Finalized Blueprints Cannot Be Modified.")

    # --- DSL 操作 (Operations) ---

    def set_frame(self):
        """
        [A-103] Frame Must Be Set First
        規則：必須緊跟在 start_blueprint 之後調用。
        """
        # 只有在 INIT 階段才能設置框架
        if self.phase != BuildPhase.INIT:
            raise SafetyViolationException("[A-103] Frame must be set immediately after start_blueprint.")
        
        self.frame = MODULE_SPECS['Frame']
        self.phase = BuildPhase.FRAME_SET # 狀態轉移 -> FRAME_SET
        return self

    def add_reactor(self, type_name):
        """安裝 Reactor (核心模組)"""
        self._check_not_finalized()
        # [A-305] 核心模組只能在鎖定前安裝
        self._check_phase([BuildPhase.FRAME_SET], "A-305")
        
        spec = self._get_spec("Reactor", type_name)
        self._check_slots(spec['slot_cost']) # [B-307] 插槽檢查
        
        self.reactors.append(spec)
        self.slots_used += spec['slot_cost']
        return self

    def add_engine(self, type_name):
        """安裝 Engine (核心模組)"""
        self._check_not_finalized()
        self._check_phase([BuildPhase.FRAME_SET], "A-305")
        
        if self.engine is not None:
            raise SafetyViolationException("Only one Engine allows.")

        spec = self._get_spec("Engine", type_name)
        self._check_slots(spec['slot_cost'])
        
        self.engine = spec
        self.slots_used += spec['slot_cost']
        return self

    def add_life_support(self, type_name):
        """安裝 LifeSupport (核心模組)"""
        self._check_not_finalized()
        self._check_phase([BuildPhase.FRAME_SET], "A-305")
        
        if self.life_support is not None:
            raise SafetyViolationException("Only one LifeSupport system allowed.")

        spec = self._get_spec("LifeSupport", type_name)
        self._check_slots(spec['slot_cost'])
        
        self.life_support = spec
        self.slots_used += spec['slot_cost']
        return self

    def add_bridge(self, type_name):
        """安裝 Bridge (核心模組)"""
        self._check_not_finalized()
        self._check_phase([BuildPhase.FRAME_SET], "A-305")
        
        if self.bridge is not None:
            raise SafetyViolationException("Only one Bridge allowed.")

        spec = self._get_spec("Bridge", type_name)
        self._check_slots(spec['slot_cost'])
        
        self.bridge = spec
        self.slots_used += spec['slot_cost']
        return self

    def lock_core_systems(self):
        """
        [B-209] Core System Integrity
        規則：必須安裝至少一個 Reactor, Engine, LifeSupport, Bridge 才能鎖定。
        """
        self._check_not_finalized()
        self._check_phase([BuildPhase.FRAME_SET], "A-305")
        
        # 檢查是否所有核心組件都已存在
        # reactors 列表不能為空，其他單例不能為 None
        if not (self.reactors and self.engine and self.life_support and self.bridge):
            raise SafetyViolationException("[B-209] Core System Integrity violated: Missing core modules.")
        
        self.phase = BuildPhase.CORE_LOCKED # 狀態轉移 -> CORE_LOCKED
        return self

    def add_shield(self, type_name):
        """
        安裝 Shield (可選模組)
        [B-440] Equipment Dependency Logic 檢查
        """
        self._check_not_finalized()
        # [A-305] 可選模組只能在鎖定後安裝
        self._check_phase([BuildPhase.CORE_LOCKED], "A-305")
        
        if self.shield is not None:
            raise SafetyViolationException("Only one Shield allowed.")

        spec = self._get_spec("Shield", type_name)
        
        # [B-440] 檢查反應堆依賴
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
        """安裝 Sensors (可選模組)"""
        self._check_not_finalized()
        self._check_phase([BuildPhase.CORE_LOCKED], "A-305")
        
        if self.sensors is not None:
            raise SafetyViolationException("Only one Sensors module allowed.")

        spec = self._get_spec("Sensors", type_name)
        self._check_slots(spec['slot_cost'])
        
        self.sensors = spec
        self.slots_used += spec['slot_cost']
        return self

    def finalize_blueprint(self):
        """
        [A-212] Finalized Blueprints Cannot Be Modified
        完成設計，返回一個不可變的規格對象。
        """
        self._check_not_finalized()
        
        # 雖然題目沒明說，但通常只有在鎖定核心後才能定稿
        # 這裡允許在 CORE_LOCKED 階段定稿
        if self.phase not in [BuildPhase.CORE_LOCKED]:
             # 如果你希望強制安裝可選模組，可以在這裡加檢查，目前假設可選模組非必須
             # 但必須至少鎖定核心系統 (隱含了 B-209 檢查)
             if self.phase == BuildPhase.FRAME_SET:
                 raise SafetyViolationException("Must lock core systems before finalizing.")
        
        # 計算最終規格數據
        final_specs = self._calculate_specs()
        
        self.phase = BuildPhase.FINALIZED # 狀態轉移 -> FINALIZED
        
        return FinalizedBlueprint(final_specs)

    def _calculate_specs(self):
        """計算所有物理屬性 (Task 2 Visualization 數據源)"""
        
        # 1. 質量計算
        total_mass = self.frame['mass']
        modules = self.reactors + [self.engine, self.life_support, self.bridge, self.shield, self.sensors]
        # 過濾掉 None (未安裝的可選模組)
        active_modules = [m for m in modules if m is not None]
        
        total_mass += sum(m['mass'] for m in active_modules)
        
        # 2. 能源計算
        total_power_output = sum(r['power_output'] for r in self.reactors)
        # 注意：Reactor 沒有 power_draw
        total_power_draw = sum(m.get('power_draw', 0) for m in active_modules)
        
        # 3. 推力計算
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
# 3. 藍圖規格與可視化 (Visualization)
# -------------------------------------------------------------------------

class FinalizedBlueprint:
    def __init__(self, specs):
        self.specs = specs

    def print_spec(self):
        """
        Task 2: Visualization
        打印格式化的 ASCII 報告。
        """
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
# 4. DSL 入口函數
# -------------------------------------------------------------------------

def start_blueprint():
    """[A-103] eDSL 的起始點"""
    return BlueprintBuilder()

# -------------------------------------------------------------------------
# 5. 測試與演示 (Testing Demo)
# -------------------------------------------------------------------------

if __name__ == "__main__":
    print("\n--- Test Case 1: Valid Design ---")
    try:
        # 使用方法鏈 (Method Chaining) 進行設計
        ship = (start_blueprint()
                .set_frame()
                .add_reactor("Fusion")
                .add_engine("Plasma")
                .add_life_support("Advanced")
                .add_bridge("Command")
                .lock_core_systems()  # [B-209] 檢查並切換階段
                .add_shield("Magnetic")
                .add_sensors("Basic")
                .finalize_blueprint())
        
        ship.print_spec() # Task 2 可視化
        print(">> Design Validated Successfully!")

    except SafetyViolationException as e:
        print(f"Design Failed: {e}")

    print("\n--- Test Case 2: Violation of [A-103] Frame First ---")
    try:
        # 錯誤：跳過 set_frame 直接加反應堆
        start_blueprint().add_reactor("Fusion")
    except SafetyViolationException as e:
        print(f"Caught Expected Error: {e}")

    print("\n--- Test Case 3: Violation of [B-440] Dependency Logic ---")
    try:
        # 錯誤：Fusion Reactor 不能配 Phase Shield
        (start_blueprint()
         .set_frame()
         .add_reactor("Fusion")
         .add_engine("Ion")
         .add_life_support("Standard")
         .add_bridge("Explorer")
         .lock_core_systems()
         .add_shield("Phase")) # 這裡應該報錯
    except SafetyViolationException as e:
        print(f"Caught Expected Error: {e}")

    print("\n--- Test Case 4: Violation of [B-209] Core Integrity ---")
    try:
        # 錯誤：缺少 Engine 就嘗試鎖定
        (start_blueprint()
         .set_frame()
         .add_reactor("Antimatter")
         # .add_engine("Ion")  <-- 缺少引擎
         .add_life_support("Standard")
         .add_bridge("Explorer")
         .lock_core_systems()) # 這裡應該報錯
    except SafetyViolationException as e:
        print(f"Caught Expected Error: {e}")