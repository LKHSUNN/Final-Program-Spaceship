import sys
import json
from abc import ABC, abstractmethod
from enum import Enum
from typing import List, Optional, Dict, Any

# 1. 例外與常量

class SafetyViolationException(Exception):
    #違反 DSL 建構規則時拋出的例外
    pass

# 模組規格定義
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

class BuildPhase:
    INIT = "INIT"
    FRAME_SET = "FRAME_SET"
    CORE_LOCKED = "CORE_LOCKED"
    FINALIZED = "FINALIZED"

class ModuleState(Enum):
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    HIGH_THRUST = "HIGH_THRUST" # Engine specific
    EMERGENCY = "EMERGENCY"     # Shield specific
    ACTIVE = "ACTIVE"           # Cooler specific
    INACTIVE = "INACTIVE"       # Cooler specific
    OFFLINE_POWER_DENIED = "OFFLINE_POWER_DENIED"
    UNAVAILABLE = "UNAVAILABLE" # Module not installed

# 2. 介面定義

class ILogger(ABC):
    @abstractmethod
    def log(self, message: str):
        pass

class IAlertSystem(ABC):
    @abstractmethod
    def alert(self, message: str):
        pass

# 3. 基礎類別

class Module:
    """簡易模組資料容器"""
    def __init__(self, category: str, spec: dict):
        self.category = category
        self.spec = spec
        self.state = ModuleState.ONLINE if category == "Reactor" else ModuleState.OFFLINE

# 4. Blueprint 建構器

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
            raise SafetyViolationException("Frame not set.")
        remaining = self.frame['total_slots'] - self.slots_used
        if cost > remaining:
            raise SafetyViolationException(f"[B-307] Slot limitation exceeded.")

    def _check_phase(self, allowed_phases, rule_id):
        if self.phase not in allowed_phases:
            raise SafetyViolationException(f"[{rule_id}] Operation not allowed in phase '{self.phase}'.")

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
        if self.engine: raise SafetyViolationException("Only one Engine allowed.")
        spec = self._get_spec("Engine", type_name)
        self._check_slots(spec['slot_cost'])
        self.engine = spec
        self.slots_used += spec['slot_cost']
        return self

    def add_life_support(self, type_name):
        self._check_not_finalized()
        self._check_phase([BuildPhase.FRAME_SET], "A-305")
        if self.life_support: raise SafetyViolationException("Only one LifeSupport allowed.")
        spec = self._get_spec("LifeSupport", type_name)
        self._check_slots(spec['slot_cost'])
        self.life_support = spec
        self.slots_used += spec['slot_cost']
        return self

    def add_bridge(self, type_name):
        self._check_not_finalized()
        self._check_phase([BuildPhase.FRAME_SET], "A-305")
        if self.bridge: raise SafetyViolationException("Only one Bridge allowed.")
        spec = self._get_spec("Bridge", type_name)
        self._check_slots(spec['slot_cost'])
        self.bridge = spec
        self.slots_used += spec['slot_cost']
        return self

    def lock_core_systems(self):
        self._check_not_finalized()
        self._check_phase([BuildPhase.FRAME_SET], "A-305")
        if not (self.reactors and self.engine and self.life_support and self.bridge):
            raise SafetyViolationException("[B-209] Missing core modules.")
        self.phase = BuildPhase.CORE_LOCKED
        return self

    def add_shield(self, type_name):
        self._check_not_finalized()
        self._check_phase([BuildPhase.CORE_LOCKED], "A-305")
        if self.shield: raise SafetyViolationException("Only one Shield allowed.")
        spec = self._get_spec("Shield", type_name)
        # 相容性檢查
        has_fusion = any(r['type'] == "Fusion" for r in self.reactors)
        has_antimatter = any(r['type'] == "Antimatter" for r in self.reactors)
        if has_fusion and type_name == "Phase":
            raise SafetyViolationException("[B-440] Fusion Reactor conflicts with Phase Shield.")
        if has_antimatter and type_name == "Magnetic":
            raise SafetyViolationException("[B-440] Antimatter Reactor conflicts with Magnetic Shield.")
        self._check_slots(spec['slot_cost'])
        self.shield = spec
        self.slots_used += spec['slot_cost']
        return self

    def add_sensors(self, type_name):
        self._check_not_finalized()
        self._check_phase([BuildPhase.CORE_LOCKED], "A-305")
        if self.sensors: raise SafetyViolationException("Only one Sensors module allowed.")
        spec = self._get_spec("Sensors", type_name)
        self._check_slots(spec['slot_cost'])
        self.sensors = spec
        self.slots_used += spec['slot_cost']
        return self

    def finalize_blueprint(self):
        self._check_not_finalized()
        if self.phase != BuildPhase.CORE_LOCKED:
            raise SafetyViolationException("Must lock core systems before finalizing.")
        
        # 轉換為動態模組實例
        modules_map = {
            "Reactor": self.reactors,
            "Engine": [self.engine] if self.engine else [],
            "LifeSupport": [self.life_support] if self.life_support else [],
            "Bridge": [self.bridge] if self.bridge else [],
            "Shield": [self.shield] if self.shield else [],
            "Sensors": [self.sensors] if self.sensors else []
        }
        dynamic_modules = {}
        for cat, specs in modules_map.items():
            if specs:
                dynamic_modules[cat] = [Module(cat, s) for s in specs]

        self.phase = BuildPhase.FINALIZED
        return SimFinalizedBlueprint(self._calculate_specs(), dynamic_modules)

    def _calculate_specs(self):
        # 基本規格計算
        active_modules = self.reactors + [self.engine, self.life_support, self.bridge, self.shield, self.sensors]
        active_modules = [m for m in active_modules if m]
        
        total_mass = self.frame['mass'] + sum(m['mass'] for m in active_modules)
        total_power_output = sum(r['power_output'] for r in self.reactors)
        total_power_draw = sum(m.get('power_draw', 0) for m in active_modules) # Static draw
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

# 5. 定稿藍圖

class SimFinalizedBlueprint:
    def __init__(self, specs: dict, modules: Dict[str, List[Module]]):
        self.specs = specs
        self.modules = modules
        self.total_power_output = specs['total_power_output']

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

# 6. 模擬器核心

class ShipSimulator:
    def __init__(self, blueprint: SimFinalizedBlueprint, logger: ILogger, alerter: IAlertSystem):
        self.logger = logger
        self.alerter = alerter
        self.blueprint = blueprint
        self.modules = blueprint.modules
        self.heat = 0
        self.num_reactors = len(self.modules.get("Reactor", []))
        self.module_states = {} # 記錄每一幀的狀態
        
        # 初始化狀態
        self._reset_states()
        for name in ["LifeSupport", "Bridge", "Sensors", "Engine", "Shield"]:
            if self.modules.get(name):
                self.module_states[name] = "ONLINE"


    def _reset_states(self):
        for cat, mods in self.modules.items():
            for m in mods:
                m.state = ModuleState.ONLINE if cat == "Reactor" else ModuleState.OFFLINE
        self.module_states = {}

    def tick(self, events_json: str) -> None:
        """Phase 1-4 Implementation [Source 7-10]"""
        try:
            events = set(json.loads(events_json)) if events_json.strip() else set()
        except Exception:
            events = set()
        
        # Request
        requests = self._phase_1_requests(events)
        
        # 預測
        cooler_req = self._phase_2_prediction(requests)
        if cooler_req: requests.append(cooler_req)
        
        # 仲裁
        accepted = self._phase_3_arbitration(requests)
        
        # 更新狀態
        self._phase_4_update(accepted)

    def _phase_1_requests(self, events):
        reqs = []

        if self.modules.get("LifeSupport"):
            reqs.append({"type": "LifeSupport", "prio": 1, "draw": 50})

        if self.modules.get("Shield"):
            if "ShieldHit" in events:
                reqs.append({"type": "Shield", "prio": 2, "draw": 300, "mode": "EMERGENCY"})
            else:
                reqs.append({"type": "Shield", "prio": 2, "draw": 100, "mode": "STANDARD"})

        if self.modules.get("Bridge"):
            reqs.append({"type": "Bridge", "prio": 4, "draw": 75})

        if self.modules.get("Engine"):
            if "EngineFullThrust" in events:
                reqs.append({"type": "Engine", "prio": 5, "draw": 500, "mode": "HIGH"})
            else:
                reqs.append({"type": "Engine", "prio": 5, "draw": 250, "mode": "STANDARD"})

        if self.modules.get("Sensors"):
            reqs.append({"type": "Sensors", "prio": 6, "draw": 50})
        return reqs

    def _phase_2_prediction(self, reqs):
        pred_delta = (4 * self.num_reactors) - (2 * self.num_reactors)
        for r in reqs:
            if r["type"] == "Engine" and r.get("mode") == "HIGH": pred_delta += 8
            if r["type"] == "Shield" and r.get("mode") == "EMERGENCY": pred_delta += 10
        
        if (self.heat + pred_delta) > 50 and self.modules.get("LifeSupport"):
            return {"type": "Cooler", "prio": 3, "draw": 150}
        return None

    def _phase_3_arbitration(self, reqs):
        # 仲裁：依優先度分配電力
        reqs.sort(key=lambda x: x["prio"])
        avail = self.blueprint.total_power_output
        accepted = {}
        
        for r in reqs:
            if avail >= r["draw"]:
                avail -= r["draw"]
                accepted[r["type"]] = r
                self.logger.log(f"PowerGranted({r['type']}, {r['draw']})")
            else:
                # 告警
                if r["type"] == "LifeSupport": self.alerter.alert("PowerDenied(LifeSupport)")
                elif r["type"] == "Shield" and r.get("mode") == "EMERGENCY": self.alerter.alert("PowerDenied(Shields)")
                elif r["type"] == "Engine" and r.get("mode") == "HIGH": self.alerter.alert("EngineThrustFailure")
                else: self.logger.log(f"PowerDenied({r['type']})")
        return accepted

    def _phase_4_update(self, accepted):
        # 更新模組狀態
        s = {}
        # 生命維持與冷卻
        if "LifeSupport" in accepted:
            s["LifeSupport"] = "ONLINE"
            if "Cooler" in accepted:
                s["Cooler"] = "ACTIVE"
                self.logger.log("CoolingEngaged")
            else:
                s["Cooler"] = "INACTIVE"
        else:
            s["LifeSupport"] = "OFFLINE_POWER_DENIED"
            s["Cooler"] = "INACTIVE"
            
        # 其他模組
        for name in ["Bridge", "Sensors"]:
            if self.modules.get(name):
                s[name] = "ONLINE" if name in accepted else "OFFLINE_POWER_DENIED"
            else:
                s[name] = "UNAVAILABLE"
                
        # Engine
        if self.modules.get("Engine"):
            if "Engine" in accepted:
                s["Engine"] = "HIGH_THRUST" if accepted["Engine"]["mode"] == "HIGH" else "ONLINE"
            else:
                s["Engine"] = "OFFLINE_POWER_DENIED"
        else:
            s["Engine"] = "UNAVAILABLE"
            
        # Shield
        if self.modules.get("Shield"):
            if "Shield" in accepted:
                s["Shield"] = "EMERGENCY" if accepted["Shield"]["mode"] == "EMERGENCY" else "ONLINE"
            else:
                s["Shield"] = "OFFLINE_POWER_DENIED"
        else:
            s["Shield"] = "UNAVAILABLE"
            
        self.module_states = s
        
        # 熱量更新
        delta = (4 * self.num_reactors) - (2 * self.num_reactors)
        if s.get("Engine") == "HIGH_THRUST": delta += 8
        if s.get("Shield") == "EMERGENCY": delta += 10
        if s.get("Cooler") == "ACTIVE": delta -= 10
        
        self.heat = max(0, self.heat + delta)
        if self.heat >= 90: self.alerter.alert("Overheat")

    def get_state_json(self):
        # 計算總耗電
        draw = 0
        s = self.module_states
        if s.get("LifeSupport") == "ONLINE": draw += 50
        if s.get("Cooler") == "ACTIVE": draw += 150
        if s.get("Bridge") == "ONLINE": draw += 75
        if s.get("Sensors") == "ONLINE": draw += 50
        
        eng = s.get("Engine")
        if eng == "ONLINE": draw += 250
        elif eng == "HIGH_THRUST": draw += 500
            
        shd = s.get("Shield")
        if shd == "ONLINE": draw += 100
        elif shd == "EMERGENCY": draw += 300
            
        return {
            "total_power_draw": draw,
            "total_power_output": self.blueprint.total_power_output,
            "heat": self.heat,
            "life_support_status": s.get("LifeSupport", "UNAVAILABLE"),
            "cooler_status": s.get("Cooler", "INACTIVE"),
            "engine_status": s.get("Engine", "UNAVAILABLE"),
            "bridge_status": s.get("Bridge", "UNAVAILABLE"),
            "shield_status": s.get("Shield", "UNAVAILABLE"),
            "sensors_status": s.get("Sensors", "UNAVAILABLE")
        }

# 7. 測試輔助類與主程式入口

class ConsoleLogger(ILogger):
    def log(self, message): print(f"[LOG] {message}", file=sys.stderr)

class ConsoleAlerter(IAlertSystem):
    def alert(self, message): print(f"[ALERT] {message}", file=sys.stderr)

def start_blueprint(): return BlueprintBuilder()

if __name__ == "__main__":
    # 建立預設藍圖並啟動模擬器
    try:
        blueprint = (start_blueprint().set_frame()
                     .add_reactor("Fusion").add_engine("Ion")
                     .add_life_support("Standard").add_bridge("Command")
                     .lock_core_systems()
                     .add_shield("Magnetic").add_sensors("Basic")
                     .finalize_blueprint())
    except Exception:
        sys.exit(1)

    logger = ConsoleLogger()
    alerter = ConsoleAlerter()
    simulator = ShipSimulator(blueprint, logger, alerter)

    # 主迴圈：接受三種命令：tick <json_events>, print_state, print_spec
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            parts = line.split(' ', 1)
            command = parts[0]
            arg = parts[1] if len(parts) > 1 else ""

            if command == "tick":
                events = arg if arg else "[]"
                simulator.tick(events)

            elif command == "print_state":
                print(json.dumps(simulator.get_state_json()))
                sys.stdout.flush()

            elif command == "print_spec":
                try:
                    blueprint.print_spec()
                except Exception:
                    print("Failed to print spec", file=sys.stderr)

            else:
                print(f"Unknown command: {command}", file=sys.stderr)
    except KeyboardInterrupt:
        print("Interrupted by user", file=sys.stderr)
        sys.exit(0)