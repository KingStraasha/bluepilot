"""Focused unit & integration tests for steering response graph UI, adjuster, and gestures."""

from dataclasses import dataclass
from enum import IntEnum
import sys, types, unittest
from unittest.mock import MagicMock, patch


def _stub(name: str, **attrs) -> types.ModuleType:
  parts = name.split(".")
  for i in range(1, len(parts)):
    parent = ".".join(parts[:i])
    if parent not in sys.modules:
      try: __import__(parent)
      except (ImportError, OSError): _stub(parent)
  mod = sys.modules.get(name) or types.ModuleType(name)
  mod.__path__ = getattr(mod, "__path__", [])
  for k, v in attrs.items(): setattr(mod, k, v)
  mod.__getattr__ = lambda _n: MagicMock()
  sys.modules[name] = mod
  if len(parts) > 1: setattr(sys.modules[".".join(parts[:-1])], parts[-1], mod)
  return mod


def _install_stubs():
  pyray_stubbed = False
  try:
    import pyray  # noqa: F401
  except (ImportError, OSError):
    pyray_stubbed = True
    @dataclass
    class Color: r: int; g: int; b: int; a: int = 255
    @dataclass
    class Rectangle: x: float = 0.0; y: float = 0.0; width: float = 0.0; height: float = 0.0
    @dataclass
    class Vector2: x: float = 0.0; y: float = 0.0
    rl = _stub(
      "pyray", Color=Color, Rectangle=Rectangle, Vector2=Vector2, Font=object, Texture=object,
      KeyboardKey=types.SimpleNamespace(KEY_ESCAPE=256, KEY_SPACE=32),
      MouseButton=types.SimpleNamespace(MOUSE_BUTTON_LEFT=0),
      BLACK=Color(0, 0, 0), WHITE=Color(255, 255, 255), RED=Color(255, 0, 0), GRAY=Color(128, 128, 128), BLANK=Color(0, 0, 0, 0),
      check_collision_point_rec=lambda p, r: r.x <= p.x <= r.x + r.width and r.y <= p.y <= r.y + r.height,
      get_collision_rec=lambda a, b: Rectangle(max(a.x, b.x), max(a.y, b.y), max(0.0, min(a.x + a.width, b.x + b.width) - max(a.x, b.x)), max(0.0, min(a.y + a.height, b.y + b.height) - max(a.y, b.y))),
      check_collision_recs=lambda a, b: a.x < b.x + b.width and a.x + a.width > b.x and a.y < b.y + b.height and a.y + a.height > b.y,
      get_time=lambda: 100.0, get_frame_time=lambda: 1.0 / 60.0, get_mouse_position=lambda: Vector2(),
      is_mouse_button_down=lambda _b: False, is_key_pressed=lambda _k: False,
    )
    for fn in ("draw_rectangle", "draw_rectangle_rec", "draw_rectangle_lines", "draw_rectangle_lines_ex",
               "draw_rectangle_rounded", "draw_rectangle_rounded_lines_ex", "draw_rectangle_gradient_h",
               "draw_line", "draw_line_ex", "draw_circle", "draw_triangle", "draw_text_ex", "draw_texture_ex",
               "draw_texture_pro", "begin_scissor_mode", "end_scissor_mode", "rl_push_matrix", "rl_pop_matrix",
               "rl_scalef", "rl_translatef"):
      setattr(rl, fn, lambda *a, **kw: None)

  import pyray as rl
  for mod in ("numpy", "openpilot.common.swaglog", "openpilot.common.hardware", "openpilot.common.constants", "openpilot.common.params",
              "openpilot.common.realtime", "openpilot.common.filter_simple", "openpilot.common.transformations.camera",
              "openpilot.common.transformations.orientation", "openpilot.cereal.log", "openpilot.cereal.custom", "openpilot.cereal.messaging",
              "openpilot.cereal.visionipc", "msgq.visionipc", "opendbc.car.structs", "opendbc.sunnypilot.car.interfaces",
              "openpilot.system.ui.lib.egl", "openpilot.system.ui.lib.multilang", "openpilot.selfdrive.locationd.calibrationd",
              "openpilot.selfdrive.controls.radard", "openpilot.selfdrive.modeld.helpers", "openpilot.selfdrive.navigation.helpers",
              "openpilot.selfdrive.navigation.renderer", "openpilot.sunnypilot.system.params_migration", "openpilot.sunnypilot.models.helpers",
              "openpilot.sunnypilot.sunnylink.sunnylink_state", "openpilot.sunnypilot.modeld_v2.blendful",
              "openpilot.sunnypilot.selfdrive.controls.lib.speed_limit.common"):
    try: __import__(mod)
    except (ImportError, OSError): _stub(mod)
  try: from opendbc.bluepilot_lateral.core.lateral_curv_ext import PrimaryLateralControl  # noqa: F401
  except ImportError: _stub("opendbc.bluepilot_lateral.core.lateral_curv_ext", PrimaryLateralControl=IntEnum("PrimaryLateralControl", {"curvature": 0, "angle": 1}))
  fs = sys.modules["openpilot.common.filter_simple"]
  if isinstance(getattr(fs, "FirstOrderFilter", None), MagicMock) or not hasattr(fs, "FirstOrderFilter"):
    class _Filter:
      def __init__(self, x0, *a, **kw): self.x = x0
      def update(self, target): self.x = target; return target
    fs.FirstOrderFilter = fs.BounceFilter = _Filter

  def _stub_application():
    FontWeight = IntEnum("FontWeight", {"NORMAL": 0, "ROMAN": 0, "MEDIUM": 1, "BOLD": 2, "SEMI_BOLD": 3, "DISPLAY": 4})
    TextAlignment = IntEnum("TextAlignment", {"LEFT": 0, "CENTER": 1, "RIGHT": 2})
    TextAlignmentVertical = IntEnum("TextAlignmentVertical", {"TOP": 0, "MIDDLE": 1, "BOTTOM": 2})
    @dataclass
    class MousePos: x: float; y: float
    @dataclass
    class MouseEvent: pos: MousePos; slot: int; left_pressed: bool; left_released: bool; left_down: bool; t: float
    class FakeGuiApp:
      width, height, target_fps, show_touches, mouse_events, _nav_stack = 2160, 1080, 20, False, [], []
      font, texture = (lambda self, _w=FontWeight.NORMAL: rl.Font()), (lambda self, *a, **kw: types.SimpleNamespace(width=64, height=64))
      sunnypilot_ui, big_ui = (lambda self: True), (lambda self: True)
      push_widget = lambda self, w: (self._nav_stack[-1].set_enabled(False) if self._nav_stack else None, self._nav_stack.append(w), w.show_event(), w.set_enabled(True)) if w not in self._nav_stack else None
      pop_widget = lambda self, idx=None: (self._nav_stack[-2].set_enabled(True), self._nav_stack.pop().hide_event()) if len(self._nav_stack) >= 2 else None
      get_active_widget, widget_in_stack = (lambda self: self._nav_stack[-1] if self._nav_stack else None), (lambda self, w: w in self._nav_stack)
    _stub("openpilot.system.ui.lib.application", gui_app=FakeGuiApp(), FontWeight=FontWeight, TextAlignment=TextAlignment,
          TextAlignmentVertical=TextAlignmentVertical, MousePos=MousePos, MouseEvent=MouseEvent, MAX_TOUCH_SLOTS=2,
          FONT_SCALE=1.0, DEFAULT_TEXT_SIZE=60, DEFAULT_TEXT_COLOR=rl.Color(255, 255, 255, 230))
    _stub("openpilot.system.ui.lib.text_measure", measure_text_cached=lambda _f, text, size, *_a: rl.Vector2(len(text) * size * 0.5, size))

  if pyray_stubbed: _stub_application()
  else:
    try: import openpilot.system.ui.lib.application  # noqa: F401
    except (ImportError, OSError): _stub_application()
  try: import openpilot.selfdrive.ui.ui_state  # noqa: F401
  except (ImportError, OSError):
    UIStatus = types.SimpleNamespace(DISENGAGED="disengaged", ENGAGED="engaged", OVERRIDE="override", LAT_ONLY="lat_only", LONG_ONLY="long_only")
    class _FakeUIState:
      started, status, sm, params, _offroad_cbs = False, UIStatus.DISENGAGED, None, MagicMock(), []
      is_onroad = lambda self: self.started
      add_offroad_transition_callback = lambda self, cb: self._offroad_cbs.append(cb)
      __getattr__ = lambda self, _n: False
    _stub("openpilot.selfdrive.ui.ui_state", UIStatus=UIStatus, ui_state=_FakeUIState(), device=types.SimpleNamespace(awake=True, set_override_interactive_timeout=lambda _t: None))
    _stub("openpilot.selfdrive.ui.sunnypilot.ui_state")
  try: import openpilot.system.ui.widgets.label  # noqa: F401
  except (ImportError, OSError):
    from openpilot.system.ui.widgets import Widget
    class _FakeLabel(Widget):
      def __init__(self, text="", *a, **kw): super().__init__(); self._text = text
      set_text, _render = (lambda self, text: setattr(self, "_text", text)), (lambda self, rect: None)
    _stub("openpilot.system.ui.widgets.label", Label=_FakeLabel, UnifiedLabel=_FakeLabel, gui_label=lambda *a, **kw: None)

  sys.modules["openpilot.selfdrive.ui"].UI_BORDER_SIZE = getattr(sys.modules.get("openpilot.selfdrive.ui"), "UI_BORDER_SIZE", 30)


_install_stubs()

import pyray as rl  # noqa: E402
from openpilot.system.ui.lib.application import MouseEvent, MousePos, gui_app  # noqa: E402
from openpilot.system.ui.widgets import Widget  # noqa: E402
from openpilot.system.ui.widgets.scroller import Scroller  # noqa: E402
from openpilot.selfdrive.ui.ui_state import device, ui_state  # noqa: E402
from openpilot.selfdrive.ui.widgets.angle_factor_adjuster import FACTOR_MAX, FACTOR_MIN, HIGH_KEY, LOW_KEY, STEP, AngleFactorAdjuster, PrimaryLateralControl  # noqa: E402
from openpilot.selfdrive.ui.widgets.steering_debug_panel import DATA_PUSH_INTERVAL, DEBUG_TIMEOUT_S, MAX_DATA_POINTS, SAFETY_TUNING_HINT, SWIPE_DOWN_THRESHOLD, SteeringDebugController, SteeringResponsePanel  # noqa: E402

class _DictParams:
  def __init__(self, initial=None): self.data, self.puts = dict(initial or {}), []
  def get(self, key, block=False, return_default=False):
    return self.data[key] if key in self.data else ({"FordPrefLateralControl": 0, LOW_KEY: 1.0, HIGH_KEY: 1.0}.get(key) if return_default else None)
  def put(self, key, val, block=False): self.data[key] = val; self.puts.append((key, val, block))

class _SM(dict):
  def __init__(self, valid, data): super().__init__(data); self.valid = valid

def _sm(desired_angle=0.0, actual_angle=0.0, v_ego=0.0, desired_curv=0.0, actual_curv=0.0, steer_delay=0.2, valid_override=None):
  return _SM({"carControl": True, "carState": True, "controlsState": True, "carParams": True, **(valid_override or {})}, {
    "carControl": types.SimpleNamespace(actuators=types.SimpleNamespace(steeringAngleDeg=desired_angle)),
    "carState": types.SimpleNamespace(steeringAngleDeg=actual_angle, vEgo=v_ego, standstill=True),
    "controlsState": types.SimpleNamespace(desiredCurvature=desired_curv, curvature=actual_curv),
    "carParams": types.SimpleNamespace(steerActuatorDelay=steer_delay),
  })

def _ev(x, y, pressed=False, down=False, released=False, t=0.0): return MouseEvent(MousePos(x, y), 0, pressed, released, down, t)

def _stub_camera_init(self, _name, stream_type):
  Widget.__init__(self)
  self._stream_type, self.available_streams, self.egl_images = stream_type, [], {}
  self.frame = self.texture_y = self.texture_uv = self.egl_texture = self.shader = self.client = self._placeholder_color = None

class TestSteeringResponseAndAdjuster(unittest.TestCase):
  def setUp(self): self._orig = (ui_state.sm, ui_state.started, list(gui_app.mouse_events))
  def tearDown(self): ui_state.sm, ui_state.started = self._orig[0], self._orig[1]; gui_app.mouse_events[:] = self._orig[2]

  def test_tici_sampling_curvature_throttle_and_bounds(self):
    with patch("openpilot.selfdrive.ui.widgets.angle_factor_adjuster.Params", return_value=_DictParams()):
      panel = SteeringResponsePanel(back_callback=lambda: None, compact=False, include_curvature=True)
    ui_state.started = True; clock = [10.0]
    with patch("openpilot.selfdrive.ui.widgets.steering_debug_panel.time.monotonic", side_effect=lambda: clock[0]):
      ui_state.sm = _sm(desired_angle=12.5, actual_angle=10.0, desired_curv=0.025, actual_curv=-0.015, steer_delay=0.275)
      panel._update_state()
      clock[0] += DATA_PUSH_INTERVAL * 0.5  # throttled at 20 Hz
      ui_state.sm = _sm(desired_angle=99.0, actual_angle=99.0, desired_curv=0.5, actual_curv=0.5)
      panel._update_state()
      self.assertEqual([len(d) for d in panel._graph._data], [1, 1, 1, 1])
      self.assertEqual([panel._graph._data[i][0] for i in range(4)], [12.5, 10.0, 2.5, -1.5])
      self.assertEqual(panel._graph._extra_legend_items, [("Steer Delay", "0.275s")])
      for idx in range(MAX_DATA_POINTS + 15):
        clock[0] += DATA_PUSH_INTERVAL + 0.001
        ui_state.sm = _sm(desired_angle=float(idx), actual_angle=float(idx) - 1.0)
        panel._update_state()
      self.assertEqual(len(panel._graph._data[0]), MAX_DATA_POINTS)
      self.assertAlmostEqual(panel._graph._data[0][0], float(MAX_DATA_POINTS + 14))

  def test_mici_angle_only_invalid_services_and_safety_hint(self):
    self.assertIn("safe setting", SAFETY_TUNING_HINT)
    ui_state.started = True
    with patch("openpilot.selfdrive.ui.widgets.angle_factor_adjuster.Params", return_value=_DictParams()):
      panel = SteeringResponsePanel(back_callback=lambda: None, compact=True, include_curvature=False)
    self.assertEqual(len(panel._graph._data), 2)
    ui_state.sm = _sm(desired_angle=8.0, actual_angle=6.0, valid_override={"carControl": False, "carState": True})
    with patch("openpilot.selfdrive.ui.widgets.steering_debug_panel.time.monotonic", return_value=20.0): panel._update_state()
    self.assertEqual([panel._graph._data[0][0], panel._graph._data[1][0]], [0.0, 6.0])

  def test_adjuster_visibility_fail_closed_defaults_and_speed_blend_clamping(self):
    params = _DictParams({"FordPrefLateralControl": int(PrimaryLateralControl.curvature)})
    with patch("openpilot.selfdrive.ui.widgets.angle_factor_adjuster.Params", return_value=params): adj = AngleFactorAdjuster()
    self.assertFalse(adj.is_visible)
    params.data["FordPrefLateralControl"] = int(PrimaryLateralControl.angle); self.assertTrue(adj.is_visible)
    for bad in ("bad", None, 99): params.data["FordPrefLateralControl"] = bad; self.assertFalse(adj.is_visible)
    params.data["FordPrefLateralControl"] = int(PrimaryLateralControl.angle)
    with patch("openpilot.selfdrive.ui.widgets.angle_factor_adjuster.PrimaryLateralControl", None): self.assertFalse(adj.is_visible)
    for bad_val in (None, "bad", b"corrupt", "nan", "inf", "-inf"): params.data[LOW_KEY] = bad_val; self.assertEqual(adj._get(LOW_KEY), 1.0)
    params.data[HIGH_KEY] = b"1.23"; self.assertAlmostEqual(adj._get(HIGH_KEY), 1.23)

    params.data[LOW_KEY] = params.data[HIGH_KEY] = 1.0
    ui_state.sm = _sm(v_ego=10.0); adj._bump(1); self.assertAlmostEqual(params.data[LOW_KEY], 1.0 + STEP); self.assertAlmostEqual(params.data[HIGH_KEY], 1.0)
    ui_state.sm = _sm(v_ego=30.0); adj._bump(-1); self.assertAlmostEqual(params.data[HIGH_KEY], 1.0 - STEP)
    params.data[LOW_KEY] = params.data[HIGH_KEY] = 1.0
    ui_state.sm = _sm(v_ego=(13.5 + 26.82) / 2.0); adj._bump(1)
    self.assertAlmostEqual(params.data[LOW_KEY], 1.0 + 0.5 * STEP); self.assertAlmostEqual(params.data[HIGH_KEY], 1.0 + 0.5 * STEP)
    params.data[LOW_KEY], params.data[HIGH_KEY] = FACTOR_MAX, FACTOR_MIN
    ui_state.sm = _sm(v_ego=0.0); adj._bump(1); self.assertEqual(params.data[LOW_KEY], FACTOR_MAX)
    ui_state.sm = _sm(v_ego=35.0); adj._bump(-1); self.assertEqual(params.data[HIGH_KEY], FACTOR_MIN)
    self.assertTrue(all(block is False for _, _, block in params.puts))


class TestGesturesAndIntegration(unittest.TestCase):
  def setUp(self): self._orig = (ui_state.started, list(gui_app.mouse_events))
  def tearDown(self): ui_state.started = self._orig[0]; gui_app.mouse_events[:] = self._orig[1]

  def test_controller_offroad_dismiss_duplicate_and_external_pop(self):
    root = MagicMock(); stack = [root]
    push = lambda w: (stack.append(w), w.show_event()) if w not in stack else None
    pop = lambda: stack.pop().hide_event() if len(stack) >= 2 else None
    with patch("openpilot.selfdrive.ui.widgets.angle_factor_adjuster.Params", return_value=_DictParams()), \
         patch.object(gui_app, "push_widget", side_effect=push), patch.object(gui_app, "pop_widget", side_effect=pop), \
         patch.object(gui_app, "widget_in_stack", side_effect=lambda w: w in stack), \
         patch.object(gui_app, "get_active_widget", side_effect=lambda: stack[-1]), \
         patch.object(device, "set_override_interactive_timeout") as mock_to:
      ctrl = SteeringDebugController(compact=True, include_curvature=False)
      ui_state.started = False; self.assertIsNone(ctrl.open_if_onroad())
      ui_state.started = True; panel = ctrl.open_if_onroad(); ctrl.open_if_onroad()
      self.assertEqual((len(stack), mock_to.call_args_list[-1].args), (2, (DEBUG_TIMEOUT_S,)))
      ui_state.started = False; panel.render(rl.Rectangle(0, 0, 536, 240))
      self.assertEqual((stack, mock_to.call_args_list[-1].args), ([root], (None,)))
      ui_state.started = True; ctrl.open_if_onroad(); ui_state.started = False; ctrl._on_offroad_transition()
      self.assertEqual(stack, [root])
      ui_state.started = True; ctrl.open_if_onroad(); stack.pop(); ctrl.dismiss()
      self.assertEqual(stack, [root]); self.assertIsNotNone(ctrl.open_if_onroad())

  def test_tici_deferred_tap_vs_downward_swipe_integration(self):
    from openpilot.selfdrive.ui.onroad.augmented_road_view import AugmentedRoadView
    ui_state.started = True; clicks, pushed = [], []
    with patch("openpilot.selfdrive.ui.onroad.cameraview.CameraView.__init__", _stub_camera_init), \
         patch("openpilot.selfdrive.ui.widgets.angle_factor_adjuster.Params", return_value=_DictParams()):
      view = AugmentedRoadView()
    rect = rl.Rectangle(0, 0, 2160, 1080); view.set_rect(rect); view.set_click_callback(lambda: clicks.append(True))
    def step(*evs):
      for ev in evs: gui_app.mouse_events[:] = [ev]; view._swipe_detector.render(rect); view._process_mouse_events()
    step(_ev(500, 200, pressed=True, down=True, t=1.0)); self.assertEqual(clicks, [])
    step(_ev(502, 204, released=True, t=1.05)); self.assertEqual(len(clicks), 1)
    with patch("openpilot.selfdrive.ui.widgets.angle_factor_adjuster.Params", return_value=_DictParams()), \
         patch.object(gui_app, "push_widget", side_effect=pushed.append), \
         patch.object(gui_app, "widget_in_stack", side_effect=lambda w: w in pushed):
      step(_ev(500, 100, pressed=True, down=True, t=2.0), _ev(505, 250, down=True, t=2.05), _ev(510, 350, released=True, t=2.1))
      ui_state.started = False
      for ev in (_ev(500, 100, pressed=True, down=True, t=3.0), _ev(505, 350, released=True, t=3.1)):
        gui_app.mouse_events[:] = [ev]; view._swipe_detector.render(rect)
    self.assertEqual((len(pushed), pushed[0]._include_curvature, len(clicks)), (1, True, 1))

  def test_mici_scroller_integration_consumes_vertical_swipe_and_preserves_horizontal_and_tap(self):
    from openpilot.selfdrive.ui.mici.onroad.augmented_road_view import AugmentedRoadView
    ui_state.started = True; taps, bookmarks, pushed = [], [], []
    home = type("HomeStub", (Widget,), {"_render": lambda self, _r: None})()
    with patch("openpilot.selfdrive.ui.mici.onroad.cameraview.CameraView.__init__", _stub_camera_init), \
         patch("openpilot.selfdrive.ui.widgets.angle_factor_adjuster.Params", return_value=_DictParams()):
      view = AugmentedRoadView(bookmark_callback=lambda: bookmarks.append(True))
    view.set_click_callback(lambda: taps.append(True))
    view._render = lambda _r: (view._bookmark_icon.render(view.rect), view._swipe_detector.render(view.rect))
    rect = rl.Rectangle(0, 0, 536, 240); home.set_rect(rect); view.set_rect(rect)
    scroller = Scroller(snap_items=True, spacing=0, pad=0, scroll_indicator=False, edge_shadows=False)
    scroller._scroller.add_widgets([home, view])
    scroller._scroller.set_scrolling_enabled(lambda: not (view.is_swiping_left() or view.is_swiping_down()))
    scroller._scroller.scroll_to(536); scroller.render(rect)
    initial_offset = scroller._scroller.scroll_panel.get_offset(); self.assertEqual(initial_offset, -536.0)
    def run(*evs):
      for ev in evs: gui_app.mouse_events[:] = [ev]; scroller.render(rect)
      gui_app.mouse_events[:] = []

    run(_ev(200, 120, pressed=True, down=True, t=1.0), _ev(202, 122, released=True, t=1.05))
    self.assertEqual((len(taps), bookmarks, pushed), (1, [], []))
    run(_ev(420, 120, pressed=True, down=True, t=2.0), _ev(240, 122, down=True, t=2.05), _ev(200, 125, released=True, t=2.1))
    self.assertEqual((len(bookmarks), len(taps), pushed), (1, 1, []))
    with patch("openpilot.selfdrive.ui.widgets.angle_factor_adjuster.Params", return_value=_DictParams()), \
         patch.object(gui_app, "push_widget", side_effect=pushed.append), \
         patch.object(gui_app, "widget_in_stack", side_effect=lambda w: w in pushed):
      run(_ev(250, 20, pressed=True, down=True, t=3.0), _ev(266, 90, down=True, t=3.05), _ev(270, 140, down=True, t=3.08))
      self.assertEqual(scroller._scroller.scroll_panel.get_offset(), initial_offset)
      run(_ev(272, 20 + SWIPE_DOWN_THRESHOLD + 40, released=True, t=3.1))
    self.assertEqual(scroller._scroller.scroll_panel.get_offset(), initial_offset)
    self.assertEqual((len(pushed), pushed[0]._include_curvature, len(taps), len(bookmarks)), (1, False, 1, 1))
    run(_ev(100, 120, pressed=True, down=True, t=4.0), _ev(140, 122, down=True, t=4.05), _ev(180, 122, down=True, t=4.1))
    self.assertGreater(scroller._scroller.scroll_panel.get_offset(), initial_offset)

  def test_mici_panel_tap_inside_adjuster_stays_open_outside_dismisses(self):
    closed = []
    with patch("openpilot.selfdrive.ui.widgets.angle_factor_adjuster.Params",
               return_value=_DictParams({"FordPrefLateralControl": int(PrimaryLateralControl.angle)})):
      panel = SteeringResponsePanel(back_callback=lambda: closed.append(True), compact=True)
    panel._adjuster_rect = rl.Rectangle(425, 5, 110, 235)
    panel._handle_mouse_release(MousePos(450, 100)); self.assertEqual(closed, [])
    panel._handle_mouse_release(MousePos(100, 100)); self.assertEqual(len(closed), 1)

if __name__ == "__main__": unittest.main()
