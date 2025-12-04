###暂时不用不考虑
from __future__ import annotations
from typing import Generic, TypeVar, Optional, List
import sys

# -------------------------------------------------------------------------
# 1. 类型定义（幻影类型 + 类型变量）
# -------------------------------------------------------------------------
# 阶段标签（幻影类型，无实际数据，仅用于静态类型检查）
class InitTag: ...
class FrameSetTag: ...
class CoreLockedTag: ...
class FinalizedTag: ...

# 类型变量，绑定阶段标签
Phase = TypeVar("Phase")

# -------------------------------------------------------------------------
# 2. 异常与常量定义
# -------------------------------------------------------------------------
class SafetyViolationException(Exception):
    """运行时异常（仅用于无法通过静态类型检测的边缘情况）"""
    pass

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

# -------------------------------------------------------------------------
# 3. DSL核心类（泛型 + 类型状态模式）
# -------------------------------------------------------------------------
class BlueprintBuilder(Generic[Phase]):
    def __init__(
        self,
        phase: type[Phase],
        frame: Optional[dict] = None,
        reactors: List[dict] = None,
        engine: Optional[dict] = None,
        life_support: Optional[dict] = None,
        bridge: Optional[dict] = None,
        shield: Optional[dict] = None,
        sensors: Optional[dict] = None,
        slots_used: int = 0
    ):
        self._phase = phase  # 阶段标签（仅用于静态类型检查）
        self.frame = frame
        self.reactors = reactors or []
        self.engine = engine
        self.life_support = life_support
        self.bridge = bridge
        self.shield = shield
        self.sensors = sensors
        self.slots_used = slots_used

    # --- 内部辅助函数 ---
    def _get_spec(self, module_category: str, module_type: str) -> dict:
        category_specs = MODULE_SPECS.get(module_category)
        if not category_specs or module_type not in category_specs:
            raise SafetyViolationException(f"Unknown module type: {module_category} - {module_type}")
        spec = category_specs[module_type].copy()
        spec['type'] = module_type
        return spec

    def _check_slots(self, cost: int) -> None:
        if not self.frame:
            raise SafetyViolationException("Frame not set. Cannot check slots.")
        remaining = self.frame['total_slots'] - self.slots_used
        if cost > remaining:
            raise SafetyViolationException(f"[B-307] Slot limitation exceeded. Required: {cost}, Available: {remaining}")

    # --- 阶段1：INIT阶段（仅允许set_frame）---
    def set_frame(self: BlueprintBuilder[InitTag]) -> BlueprintBuilder[FrameSetTag]:
        """
        [A-103] 仅INIT阶段可调用，设置框架后进入FRAME_SET阶段
        mypy会静态检查：若当前阶段不是InitTag，直接报错
        """
        if self.frame:
            raise SafetyViolationException("[A-103] Frame already set.")
        frame = MODULE_SPECS['Frame']
        return BlueprintBuilder[FrameSetTag](
            phase=FrameSetTag,
            frame=frame,
            reactors=self.reactors,
            engine=self.engine,
            life_support=self.life_support,
            bridge=self.bridge,
            shield=self.shield,
            sensors=self.sensors,
            slots_used=self.slots_used
        )

    # --- 阶段2：FRAME_SET阶段（仅允许安装核心模块 + lock_core_systems）---
    def add_reactor(self: BlueprintBuilder[FrameSetTag], type_name: str) -> BlueprintBuilder[FrameSetTag]:
        """[A-305] 仅FRAME_SET阶段可安装核心模块"""
        spec = self._get_spec("Reactor", type_name)
        self._check_slots(spec['slot_cost'])
        self.reactors.append(spec)
        self.slots_used += spec['slot_cost']
        return self  # 阶段保持不变

    def add_engine(self: BlueprintBuilder[FrameSetTag], type_name: str) -> BlueprintBuilder[FrameSetTag]:
        if self.engine:
            raise SafetyViolationException("Only one Engine allowed.")
        spec = self._get_spec("Engine", type_name)
        self._check_slots(spec['slot_cost'])
        self.engine = spec
        self.slots_used += spec['slot_cost']
        return self

    def add_life_support(self: BlueprintBuilder[FrameSetTag], type_name: str) -> BlueprintBuilder[FrameSetTag]:
        if self.life_support:
            raise SafetyViolationException("Only one LifeSupport system allowed.")
        spec = self._get_spec("LifeSupport", type_name)
        self._check_slots(spec['slot_cost'])
        self.life_support = spec
        self.slots_used += spec['slot_cost']
        return self

    def add_bridge(self: BlueprintBuilder[FrameSetTag], type_name: str) -> BlueprintBuilder[FrameSetTag]:
        if self.bridge:
            raise SafetyViolationException("Only one Bridge allowed.")
        spec = self._get_spec("Bridge", type_name)
        self._check_slots(spec['slot_cost'])
        self.bridge = spec
        self.slots_used += spec['slot_cost']
        return self

    def lock_core_systems(self: BlueprintBuilder[FrameSetTag]) -> BlueprintBuilder[CoreLockedTag]:
        """
        [B-209] 仅FRAME_SET阶段可调用，检查核心模块完整性后进入CORE_LOCKED阶段
        """
        if not (self.reactors and self.engine and self.life_support and self.bridge):
            raise SafetyViolationException("[B-209] Core System Integrity violated: Missing core modules.")
        return BlueprintBuilder[CoreLockedTag](
            phase=CoreLockedTag,
            frame=self.frame,
            reactors=self.reactors,
            engine=self.engine,
            life_support=self.life_support,
            bridge=self.bridge,
            shield=self.shield,
            sensors=self.sensors,
            slots_used=self.slots_used
        )

    # --- 阶段3：CORE_LOCKED阶段（仅允许安装可选模块 + finalize_blueprint）---
    def add_shield(self: BlueprintBuilder[CoreLockedTag], type_name: str) -> BlueprintBuilder[CoreLockedTag]:
        """
        [A-305] 仅CORE_LOCKED阶段可安装可选模块
        [B-440] 静态检查反应堆与护盾依赖（运行时兜底）
        """
        if self.shield:
            raise SafetyViolationException("Only one Shield allowed.")
        spec = self._get_spec("Shield", type_name)
        # [B-440] 依赖检查（Python无法完全静态实现，运行时兜底）
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

    def add_sensors(self: BlueprintBuilder[CoreLockedTag], type_name: str) -> BlueprintBuilder[CoreLockedTag]:
        if self.sensors:
            raise SafetyViolationException("Only one Sensors module allowed.")
        spec = self._get_spec("Sensors", type_name)
        self._check_slots(spec['slot_cost'])
        self.sensors = spec
        self.slots_used += spec['slot_cost']
        return self

    def finalize_blueprint(self: BlueprintBuilder[CoreLockedTag]) -> FinalizedBlueprint:
        """[A-212] 仅CORE_LOCKED阶段可定稿，定稿后进入FINALIZED阶段"""
        final_specs = self._calculate_specs()
        return FinalizedBlueprint(final_specs)

    # --- 辅助函数：计算规格 ---
    def _calculate_specs(self) -> dict:
        total_mass = self.frame['mass'] if self.frame else 0
        modules = self.reactors + [self.engine, self.life_support, self.bridge, self.shield, self.sensors]
        active_modules = [m for m in modules if m]
        total_mass += sum(m['mass'] for m in active_modules)

        total_power_output = sum(r['power_output'] for r in self.reactors)
        total_power_draw = sum(m.get('power_draw', 0) for m in active_modules)
        total_thrust = self.engine['thrust'] if self.engine else 0

        return {
            "total_slots": self.frame['total_slots'] if self.frame else 0,
            "slots_used": self.slots_used,
            "total_mass": total_mass,
            "total_power_output": total_power_output,
            "total_power_consumption": total_power_draw,
            "power_balance": total_power_output - total_power_draw,
            "thrust_to_weight_ratio": total_thrust / total_mass if total_mass > 0 else 0
        }

# -------------------------------------------------------------------------
# 4. 定稿蓝图与可视化（保持不变）
# -------------------------------------------------------------------------
class FinalizedBlueprint:
    def __init__(self, specs: dict):
        self.specs = specs

    def print_spec(self):
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
# 5. DSL入口函数（初始阶段为INIT）
# -------------------------------------------------------------------------
def start_blueprint() -> BlueprintBuilder[InitTag]:
    """[A-103] 启动蓝图，初始阶段为INIT"""
    return BlueprintBuilder[InitTag](phase=InitTag)

# -------------------------------------------------------------------------
# 6. 测试与演示（静态错误需用mypy检测）
# -------------------------------------------------------------------------
if __name__ == "__main__":
    # 测试1：合法设计（无静态错误，运行正常）
    print("\n--- Test Case 1: Valid Design ---")
    try:
        ship = (start_blueprint()
                .set_frame()  # INIT -> FRAME_SET
                .add_reactor("Fusion")  # FRAME_SET阶段合法
                .add_engine("Plasma")
                .add_life_support("Advanced")
                .add_bridge("Command")
                .lock_core_systems()  # FRAME_SET -> CORE_LOCKED
                .add_shield("Magnetic")  # CORE_LOCKED阶段合法
                .add_sensors("Basic")
                .finalize_blueprint())
        ship.print_spec()
        print(">> Design Validated Successfully!")
    except SafetyViolationException as e:
        print(f"Design Failed: {e}")

    # 测试2：静态错误（INIT阶段直接add_reactor，mypy会报错）
    print("\n--- Test Case 2: Static Violation of [A-103] ---")
    try:
        # 以下代码在IDE中会显示红线，运行mypy会提示：
        # error: Argument 1 to "add_reactor" of "BlueprintBuilder" has incompatible type "BlueprintBuilder[InitTag]"; expected "BlueprintBuilder[FrameSetTag]"
        start_blueprint().add_reactor("Fusion")
    except Exception as e:
        print(f"Caught Error: {e}")

    # 测试3：静态错误（CORE_LOCKED阶段安装核心模块，mypy会报错）
    print("\n--- Test Case 3: Static Violation of [A-305] ---")
    try:
        builder = (start_blueprint()
                   .set_frame()
                   .lock_core_systems())  # 进入CORE_LOCKED阶段
        # 以下代码mypy报错：
        # error: Argument 1 to "add_engine" of "BlueprintBuilder" has incompatible type "BlueprintBuilder[CoreLockedTag]"; expected "BlueprintBuilder[FrameSetTag]"
        builder.add_engine("Ion")
    except Exception as e:
        print(f"Caught Error: {e}")