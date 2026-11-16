"""
Steering response graph screen and downward-swipe detector.

Angle-factor tuning can change steering response; tune only in a safe setting,
not while driving.
"""

from collections.abc import Callable
import time
import pyray as rl

from openpilot.selfdrive.ui.ui_state import device, ui_state
from openpilot.selfdrive.ui.widgets.angle_factor_adjuster import AngleFactorAdjuster
from openpilot.selfdrive.ui.widgets.debug_graph import DebugColors, GraphConfig, GraphSeries, TimeSeriesGraph
from openpilot.system.ui.lib.application import FontWeight, gui_app
from openpilot.system.ui.widgets import Widget
from openpilot.system.ui.widgets.button import Button

SWIPE_DOWN_THRESHOLD = 80
SWIPE_START_PX = 12

DATA_PUSH_INTERVAL = 0.05  # 20 Hz
MAX_DATA_POINTS = 100
DEBUG_TIMEOUT_S = 300

_TICI_ADJUSTER_WIDTH = 170
_TICI_ADJUSTER_MARGIN_TOP = 15
_TICI_ADJUSTER_MARGIN_RIGHT = 15
_TICI_FOOTER_HEIGHT = 100
_TICI_CLOSE_BTN_WIDTH = 180
_TICI_CLOSE_BTN_HEIGHT = 68
_TICI_CLOSE_BTN_MARGIN = 16

_COMPACT_ADJUSTER_WIDTH = 110
_COMPACT_ADJUSTER_MARGIN_TOP = 5
_COMPACT_ADJUSTER_MARGIN_RIGHT = 5

SAFETY_TUNING_HINT = "Angle-factor tuning can change steering response; tune only in a safe setting, not while driving."


class VerticalSwipeDetector(Widget):
  """Transparent overlay that detects downward swipe gestures on the on-road view."""

  def __init__(self, callback: Callable[[], None]):
    super().__init__()
    self._callback = callback
    self._interacting = False
    self._swiping_down = False
    self._press_x = 0.0
    self._press_y = 0.0
    self._tracking = False

  @staticmethod
  def _classify_drag(dx: float, dy: float, current: bool) -> bool:
    if dy > SWIPE_START_PX and dy > dx:
      return True
    if dx > SWIPE_START_PX and dx >= dy:
      return False
    return current

  def is_swiping_down(self) -> bool:
    """Return True while an active downward drag is in progress."""
    if not gui_app.mouse_events or not ui_state.started:
      return self._swiping_down
    tracking = self._tracking
    press_x, press_y = self._press_x, self._press_y
    swiping = self._swiping_down
    for ev in gui_app.mouse_events:
      if ev.slot != 0:
        continue
      if ev.left_pressed and self.enabled and self.is_visible and rl.check_collision_point_rec(ev.pos, self._hit_rect):
        tracking, press_x, press_y, swiping = True, ev.pos.x, ev.pos.y, False
      elif tracking and (ev.left_down or ev.left_released):
        swiping = self._classify_drag(abs(ev.pos.x - press_x), ev.pos.y - press_y, swiping)
    return swiping

  def interacting(self) -> bool:
    """Consume and return whether the latest release completed a downward swipe."""
    interacting, self._interacting = self._interacting, False
    return interacting

  def _handle_mouse_event(self, mouse_event):
    if mouse_event.left_pressed:
      self._interacting = False
      self._swiping_down = False
      if not ui_state.started:
        self._tracking = False
        return
      self._press_x = mouse_event.pos.x
      self._press_y = mouse_event.pos.y
      self._tracking = True
    elif mouse_event.left_down and self._tracking:
      if not ui_state.started:
        self._tracking = False
        self._swiping_down = False
        return
      self._swiping_down = self._classify_drag(
        abs(mouse_event.pos.x - self._press_x),
        mouse_event.pos.y - self._press_y,
        self._swiping_down,
      )
    elif mouse_event.left_released and self._tracking:
      self._tracking = False
      self._swiping_down = False
      if not ui_state.started:
        return
      dy = mouse_event.pos.y - self._press_y
      dx = abs(mouse_event.pos.x - self._press_x)
      if dy > SWIPE_DOWN_THRESHOLD and dy > dx:
        self._interacting = True
        self._callback()

  def _render(self, rect: rl.Rectangle):
    pass


class SteeringDebugController:
  """Manages pushing/dismissing SteeringResponsePanel safely against duplicates and stale state."""

  def __init__(self, compact: bool = False, include_curvature: bool | None = None):
    self._compact = compact
    self._include_curvature = include_curvature
    self._panel: SteeringResponsePanel | None = None
    if hasattr(ui_state, "add_offroad_transition_callback"):
      ui_state.add_offroad_transition_callback(self._on_offroad_transition)

  def _on_offroad_transition(self) -> None:
    if not ui_state.is_onroad():
      self.dismiss()

  @property
  def panel(self) -> SteeringResponsePanel | None:
    return self._panel

  def open_if_onroad(self) -> SteeringResponsePanel | None:
    if not ui_state.is_onroad():
      return None
    if self._panel is not None and gui_app.widget_in_stack(self._panel):
      return self._panel

    panel = SteeringResponsePanel(
      back_callback=self.dismiss,
      compact=self._compact,
      include_curvature=self._include_curvature,
    )
    self._panel = panel
    gui_app.push_widget(panel)
    return panel

  def dismiss(self) -> None:
    target = self._panel
    if target is None:
      return
    if gui_app.get_active_widget() is target:
      self._panel = None
      gui_app.pop_widget()
    elif not gui_app.widget_in_stack(target):
      self._panel = None


class SteeringResponsePanel(Widget):
  """Full-screen steering desired-vs-actual response graph and optional angle-factor adjuster."""

  def __init__(self, back_callback: Callable[[], None], compact: bool = False,
               include_curvature: bool | None = None):
    super().__init__()
    self._back_callback = back_callback
    self._compact = compact
    self._include_curvature = (not compact) if include_curvature is None else include_curvature
    self._adjuster = self._child(AngleFactorAdjuster(compact=compact))
    self._adjuster_rect = rl.Rectangle(0, 0, 0, 0)
    self._close_btn = None if compact else self._child(Button("Close", self._dismiss, font_size=38))

    if self._include_curvature:
      series = [
        GraphSeries("Angle Desired", DebugColors.DESIRED_GREEN, fill_alpha=25),
        GraphSeries("Angle Actual", DebugColors.ACTUAL_YELLOW, fill_alpha=25, beaded=True),
        GraphSeries("Desired Curv", DebugColors.DESIRED_CURV_CYAN),
        GraphSeries("Actual Curv", DebugColors.ACTUAL_CURV_MAGENTA),
      ]
    else:
      series = [
        GraphSeries("Desired", DebugColors.DESIRED_GREEN, fill_alpha=25),
        GraphSeries("Actual", DebugColors.ACTUAL_YELLOW, fill_alpha=25, beaded=True),
      ]

    if compact:
      config = GraphConfig(
        title="Steering Angle",
        y_unit="\u00b0",
        max_data_points=MAX_DATA_POINTS,
        min_scale=5.0,
        title_font_size=21,
        axis_font_size=16,
        legend_font_size=16,
        legend_y_offset=-20,
        marker_radius=4.5,
      )
    else:
      config = GraphConfig(
        title="Lateral Control",
        y_unit="\u00b0",
        max_data_points=MAX_DATA_POINTS,
        min_scale=5.0,
        legend_font_size=20,
      )

    self._graph = TimeSeriesGraph(config=config, series=series)
    self._steer_delay = 0.0
    self._last_push_time: float | None = None
    self._font_normal = gui_app.font(FontWeight.NORMAL)

  def show_event(self):
    super().show_event()
    device.set_override_interactive_timeout(DEBUG_TIMEOUT_S)

  def hide_event(self):
    super().hide_event()
    device.set_override_interactive_timeout(None)

  def _dismiss(self):
    self._back_callback()

  def _update_state(self):
    if not ui_state.is_onroad():
      self._dismiss()
      return
    sm = ui_state.sm
    if sm is None:
      return

    now = time.monotonic()
    if self._last_push_time is not None and now - self._last_push_time < DATA_PUSH_INTERVAL:
      return

    desired_angle = 0.0
    actual_angle = 0.0
    desired_curv = 0.0
    actual_curv = 0.0

    try:
      if sm.valid.get('carControl', False):
        desired_angle = float(sm['carControl'].actuators.steeringAngleDeg)
      if sm.valid.get('carState', False):
        actual_angle = float(sm['carState'].steeringAngleDeg)

      if self._include_curvature:
        if sm.valid.get('controlsState', False):
          cs = sm['controlsState']
          actual_curv = float(cs.curvature)
          desired_curv = float(cs.desiredCurvature)
        if sm.valid.get('carParams', False):
          self._steer_delay = float(sm['carParams'].steerActuatorDelay)

        self._graph.push_data([
          desired_angle,
          actual_angle,
          desired_curv * 100.0,
          actual_curv * 100.0,
        ])
        self._graph.set_extra_legend([
          ("Steer Delay", f"{self._steer_delay:.3f}s"),
        ])
      else:
        self._graph.push_data([desired_angle, actual_angle])

      self._last_push_time = now
    except (KeyError, AttributeError, ValueError):
      pass

  def _handle_mouse_release(self, mouse_pos):
    if self._compact:
      if self._adjuster.is_visible and rl.check_collision_point_rec(mouse_pos, self._adjuster_rect):
        return
      self._dismiss()

  def _render(self, rect: rl.Rectangle):
    if not ui_state.is_onroad():
      self._dismiss()
      return
    rl.draw_rectangle(int(rect.x), int(rect.y), int(rect.width), int(rect.height), DebugColors.PANEL_BG)

    if self._compact:
      self._graph.render(rect)
      adjuster_w = _COMPACT_ADJUSTER_WIDTH if self._adjuster.is_visible else 0
      self._adjuster_rect = rl.Rectangle(
        rect.x + rect.width - adjuster_w - _COMPACT_ADJUSTER_MARGIN_RIGHT,
        rect.y + _COMPACT_ADJUSTER_MARGIN_TOP,
        adjuster_w,
        rect.height - _COMPACT_ADJUSTER_MARGIN_TOP,
      )
      self._adjuster.render(self._adjuster_rect)

      rl.draw_text_ex(self._font_normal, "tap to close",
                      rl.Vector2(rect.x + 20, rect.y + rect.height - 40),
                      30, 0, rl.Color(110, 110, 110, 180))
      return

    if rl.is_key_pressed(rl.KeyboardKey.KEY_ESCAPE):
      self._dismiss()
      return

    content_rect = rl.Rectangle(rect.x, rect.y, rect.width, rect.height - _TICI_FOOTER_HEIGHT)
    self._graph.render(content_rect)

    adjuster_w = _TICI_ADJUSTER_WIDTH if self._adjuster.is_visible else 0
    self._adjuster_rect = rl.Rectangle(
      content_rect.x + content_rect.width - adjuster_w - _TICI_ADJUSTER_MARGIN_RIGHT,
      content_rect.y + _TICI_ADJUSTER_MARGIN_TOP,
      adjuster_w,
      content_rect.height - _TICI_ADJUSTER_MARGIN_TOP,
    )
    self._adjuster.render(self._adjuster_rect)

    footer_y = rect.y + rect.height - _TICI_FOOTER_HEIGHT
    footer_rect = rl.Rectangle(rect.x, footer_y, rect.width, _TICI_FOOTER_HEIGHT)
    rl.draw_rectangle_rec(footer_rect, DebugColors.PANEL_BG_DARKER)
    rl.draw_line(int(footer_rect.x), int(footer_y),
                 int(footer_rect.x + footer_rect.width), int(footer_y),
                 DebugColors.FOOTER_BORDER)

    btn_rect = rl.Rectangle(
      rect.x + _TICI_CLOSE_BTN_MARGIN,
      footer_y + (_TICI_FOOTER_HEIGHT - _TICI_CLOSE_BTN_HEIGHT) / 2,
      _TICI_CLOSE_BTN_WIDTH,
      _TICI_CLOSE_BTN_HEIGHT,
    )
    if self._close_btn is not None:
      self._close_btn.render(btn_rect)

    hint_x = btn_rect.x + btn_rect.width + 24
    hint_y = footer_y + (_TICI_FOOTER_HEIGHT - 28) / 2
    rl.draw_text_ex(self._font_normal, SAFETY_TUNING_HINT,
                    rl.Vector2(hint_x, hint_y), 24, 0, DebugColors.LEGEND_LABEL)
