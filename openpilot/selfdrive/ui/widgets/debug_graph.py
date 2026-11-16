"""
Time-series graph widget and colors for the steering response debug screen.
"""

import collections
import math
from dataclasses import dataclass
import pyray as rl

from openpilot.system.ui.lib.application import gui_app, FontWeight
from openpilot.system.ui.widgets import Widget


class DebugColors:
  """Color constants for steering response graph and angle-factor adjuster."""

  # Panel backgrounds
  PANEL_BG = rl.Color(15, 15, 20, 255)
  PANEL_BG_DARKER = rl.Color(20, 20, 20, 230)

  # Graph container
  GRAPH_CONTAINER_MID = rl.Color(32, 33, 35, 220)

  # Graph area background
  GRAPH_BG = rl.Color(20, 25, 30, 200)
  GRAPH_BORDER = rl.Color(0, 0, 0, 100)

  # Graph data lines
  DESIRED_GREEN = rl.Color(0, 255, 0, 200)
  ACTUAL_YELLOW = rl.Color(255, 255, 0, 200)
  DESIRED_CURV_CYAN = rl.Color(0, 255, 255, 200)
  ACTUAL_CURV_MAGENTA = rl.Color(255, 100, 255, 200)

  # Grid and scale
  GRID_LINE = rl.Color(189, 195, 199, 80)
  ZERO_LINE = rl.Color(236, 240, 241, 255)
  SCALE_TEXT = rl.Color(236, 240, 241, 230)
  TIME_MARKER_PRIMARY = rl.Color(180, 180, 180, 140)
  TIME_MARKER_SECONDARY = rl.Color(160, 160, 160, 110)

  # Sliding speed-position indicator (angle-factor adjuster)
  SPEED_HIGHLIGHT = rl.Color(70, 130, 180, 90)

  # Footer / border / legend
  FOOTER_BORDER = rl.Color(60, 60, 60, 150)
  LEGEND_TEXT = rl.Color(255, 255, 255, 255)
  LEGEND_LABEL = rl.Color(180, 180, 180, 255)


@dataclass
class GraphSeries:
  """Definition of a single data series on the graph."""

  label: str
  color: rl.Color
  line_width: float = 3.0
  fill_alpha: int = 0
  # Bead small circles along the line every MARKER_STRIDE points so paired series
  # stay visually distinguishable for red-green colorblind users.
  beaded: bool = False


@dataclass
class GraphConfig:
  """Configuration for a TimeSeriesGraph."""

  title: str
  y_unit: str = ""
  max_data_points: int = 100
  points_per_second: int = 20
  auto_scale: bool = True
  min_scale: float = 5.0
  scale_damping: float = 0.99
  zero_at_bottom: bool = False
  max_time_seconds: int = 5
  title_font_size: int = 52
  axis_font_size: int = 40
  legend_font_size: int = 16
  legend_y_offset: int = 0
  marker_radius: float = 9.0


class TimeSeriesGraph(Widget):
  """Time-series graph widget with auto-scaling, grid, time markers, and legend."""

  TOP_MARGIN = 58
  BOTTOM_MARGIN = 15
  SIDE_MARGIN = 85
  TIME_LABELS_HEIGHT = 46
  LEGEND_ROW_HEIGHT = 26
  LEGEND_GAP = 8
  MIN_GRAPH_HEIGHT = 80
  MARKER_STRIDE = 5

  def __init__(self, config: GraphConfig, series: list[GraphSeries]):
    super().__init__()
    self._config = config
    self._series = series
    self._data: list[collections.deque[float]] = [
      collections.deque(maxlen=config.max_data_points) for _ in series
    ]
    self._max_scale = config.min_scale
    self._font_bold = gui_app.font(FontWeight.BOLD)
    self._font_semi = gui_app.font(FontWeight.SEMI_BOLD)
    self._font_normal = gui_app.font(FontWeight.NORMAL)
    self._current_values: list[float] = [0.0] * len(series)
    self._extra_legend_items: list[tuple[str, str]] = []

  def push_data(self, values: list[float]):
    """Push a new data point for each series (newest sample at index 0)."""
    for i, val in enumerate(values):
      if i < len(self._data):
        clean_val = float(val) if math.isfinite(val) else 0.0
        self._data[i].appendleft(clean_val)
        self._current_values[i] = clean_val
    if self._config.auto_scale:
      self._update_scale()

  def set_extra_legend(self, items: list[tuple[str, str]]):
    """Set additional label/value pairs shown in the legend (no plot line)."""
    self._extra_legend_items = items

  def _update_scale(self):
    """Auto-adjust Y scale with damping."""
    for data in self._data:
      for val in data:
        abs_val = abs(val)
        if abs_val > self._max_scale:
          self._max_scale = abs_val * 1.2

    if all(len(d) > 10 for d in self._data):
      current_max = 0.0
      for data in self._data:
        for val in data:
          current_max = max(current_max, abs(val))
      if current_max < self._max_scale * 0.7:
        self._max_scale *= self._config.scale_damping

    self._max_scale = max(self._max_scale, self._config.min_scale)

  def _render(self, rect: rl.Rectangle):
    total_legend_items = len(self._series) + len(self._extra_legend_items)
    legend_rows = max(1, (total_legend_items + 2) // 3)
    legend_h = legend_rows * self.LEGEND_ROW_HEIGHT + self.LEGEND_GAP
    graph_h = int(rect.height - self.TOP_MARGIN - self.BOTTOM_MARGIN - self.TIME_LABELS_HEIGHT - legend_h)
    graph_h = max(self.MIN_GRAPH_HEIGHT, graph_h)

    graph_x = int(rect.x + self.SIDE_MARGIN)
    graph_w = int(rect.width - 2 * self.SIDE_MARGIN)
    graph_y = int(rect.y + self.TOP_MARGIN)
    time_labels_y = graph_y + graph_h + 12
    legend_y = time_labels_y + self.TIME_LABELS_HEIGHT + self.LEGEND_GAP + self._config.legend_y_offset

    self._draw_container(rect)

    rl.draw_text_ex(self._font_bold, self._config.title,
                    rl.Vector2(graph_x, rect.y + 8), self._config.title_font_size, 0,
                    DebugColors.SCALE_TEXT)

    rl.draw_rectangle(graph_x, graph_y, graph_w, graph_h, DebugColors.GRAPH_BG)
    rl.draw_rectangle_lines(graph_x, graph_y, graph_w, graph_h, DebugColors.GRAPH_BORDER)

    rl.begin_scissor_mode(graph_x, graph_y, graph_w, graph_h)

    self._draw_grid(graph_x, graph_y, graph_w, graph_h)

    if self._config.zero_at_bottom:
      zero_y = graph_y + graph_h
    else:
      zero_y = graph_y + graph_h // 2
    rl.draw_line_ex(rl.Vector2(graph_x, zero_y),
                    rl.Vector2(graph_x + graph_w, zero_y),
                    2.0, DebugColors.ZERO_LINE)

    for i, series in enumerate(self._series):
      self._draw_series(i, series, graph_x, graph_y, graph_w, graph_h, zero_y)

    rl.end_scissor_mode()

    self._draw_time_markers(graph_x, graph_y, graph_w, graph_h, time_labels_y)
    self._draw_scale(rect, graph_x, graph_y, graph_h, zero_y)
    self._draw_legend(graph_x, graph_w, legend_y)

  def _draw_container(self, rect: rl.Rectangle):
    container = rl.Rectangle(rect.x + 8, rect.y + 8, rect.width - 16, rect.height - 16)
    rl.draw_rectangle_rounded(container, 0.04, 10, DebugColors.GRAPH_CONTAINER_MID)
    rl.draw_rectangle_rounded_lines_ex(container, 0.04, 10, 1.5, rl.Color(70, 130, 180, 120))

  def _draw_grid(self, gx: int, gy: int, gw: int, gh: int):
    divisions = 8 if not self._config.zero_at_bottom else 4
    center = divisions // 2

    for i in range(1, divisions):
      if not self._config.zero_at_bottom and i == center:
        continue
      y = gy + (i * gh // divisions)
      x = gx
      while x < gx + gw:
        dash_len = min(6, gx + gw - x)
        rl.draw_line_ex(rl.Vector2(x, y), rl.Vector2(x + dash_len, y),
                        1.0, DebugColors.GRID_LINE)
        x += 12

  def _draw_time_markers(self, gx: int, gy: int, gw: int, gh: int, labels_y: int):
    max_points = self._config.max_data_points
    max_len = max((len(d) for d in self._data), default=1)
    max_len = max(1, max_len)
    point_spacing = gw / min(max_points, max_len)
    line_spacing = self._config.points_per_second * point_spacing

    for i in range(self._config.max_time_seconds + 1):
      x = gx + gw - int(i * line_spacing)
      if x < gx:
        break

      color = DebugColors.TIME_MARKER_PRIMARY if i <= 5 else DebugColors.TIME_MARKER_SECONDARY
      y = gy
      while y < gy + gh:
        dash_len = min(6, gy + gh - y)
        rl.draw_line_ex(rl.Vector2(x, y), rl.Vector2(x, y + dash_len), 1.0, color)
        y += 12

      label = "Now" if i == 0 else f"-{i}s"
      rl.draw_text_ex(self._font_normal, label,
                      rl.Vector2(x - 10, labels_y), self._config.axis_font_size, 0, DebugColors.LEGEND_TEXT)

  def _draw_scale(self, rect: rl.Rectangle, gx: int, gy: int, gh: int, zero_y: int):
    scale_x = int(rect.x + 4)
    font_size = self._config.axis_font_size

    if self._config.zero_at_bottom:
      rl.draw_text_ex(self._font_semi, "0.0",
                      rl.Vector2(scale_x, gy + gh - 14), font_size, 0, DebugColors.SCALE_TEXT)
      rl.draw_text_ex(self._font_semi, "1.0",
                      rl.Vector2(scale_x, gy + 2), font_size, 0, DebugColors.SCALE_TEXT)
      rl.draw_text_ex(self._font_semi, "0.5",
                      rl.Vector2(scale_x, gy + gh // 2 - 6), font_size, 0, DebugColors.SCALE_TEXT)
    else:
      unit = self._config.y_unit
      rl.draw_text_ex(self._font_semi, f"0{unit}",
                      rl.Vector2(scale_x, zero_y - 6), font_size, 0, DebugColors.SCALE_TEXT)
      rl.draw_text_ex(self._font_semi, f"+{self._max_scale:.0f}{unit}",
                      rl.Vector2(scale_x, gy + 2), font_size, 0, DebugColors.SCALE_TEXT)
      rl.draw_text_ex(self._font_semi, f"-{self._max_scale:.0f}{unit}",
                      rl.Vector2(scale_x, gy + gh - 14), font_size, 0, DebugColors.SCALE_TEXT)

  def _draw_series(self, series_idx: int, series: GraphSeries,
                   gx: int, gy: int, gw: int, gh: int, zero_y: int):
    data = self._data[series_idx]
    if len(data) < 2:
      return

    max_len = max((len(d) for d in self._data), default=1)
    max_len = max(1, max_len)
    point_spacing = gw / min(self._config.max_data_points, max_len)

    points = []
    for i in range(len(data)):
      x = gx + gw - i * point_spacing
      if x < gx:
        break

      if self._config.zero_at_bottom:
        y = gy + gh - (data[i] * gh)
      else:
        y = zero_y - (data[i] / self._max_scale) * (gh / 2)

      y = max(gy, min(y, gy + gh))
      points.append((x, y))

    if len(points) < 2:
      return

    if series.fill_alpha > 0:
      fill_color = rl.Color(series.color.r, series.color.g, series.color.b, series.fill_alpha)
      base_y = float(zero_y if not self._config.zero_at_bottom else gy + gh)
      for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        rl.draw_triangle(rl.Vector2(x1, y1), rl.Vector2(x2, base_y),
                         rl.Vector2(x2, y2), fill_color)
        rl.draw_triangle(rl.Vector2(x1, y1), rl.Vector2(x1, base_y),
                         rl.Vector2(x2, base_y), fill_color)

    for i in range(len(points) - 1):
      x1, y1 = points[i]
      x2, y2 = points[i + 1]
      rl.draw_line_ex(rl.Vector2(x1, y1), rl.Vector2(x2, y2),
                      series.line_width, series.color)

    if series.beaded:
      for i in range(0, len(points), self.MARKER_STRIDE):
        x, y = points[i]
        rl.draw_circle(int(x), int(y), self._config.marker_radius, series.color)

  def _draw_legend(self, gx: int, gw: int, legend_y: int):
    font_size = self._config.legend_font_size
    col_width = gw // 3

    all_items: list[tuple[rl.Color | None, str]] = []
    for i, series in enumerate(self._series):
      val = self._current_values[i] if i < len(self._current_values) else 0.0
      unit = self._config.y_unit
      if self._config.zero_at_bottom:
        text = f"{series.label}: {val:.3f}"
      else:
        text = f"{series.label}: {val:.1f}{unit}"
      all_items.append((series.color, text))

    for label, value in self._extra_legend_items:
      all_items.append((None, f"{label}: {value}"))

    for idx, (color, text) in enumerate(all_items):
      col = idx % 3
      row = idx // 3
      x = gx + col * col_width
      y = legend_y + row * self.LEGEND_ROW_HEIGHT

      if color is not None:
        rl.draw_rectangle(x, y, 16, 16, color)
        rl.draw_text_ex(self._font_normal, text,
                        rl.Vector2(x + 22, y - 2), font_size, 0, DebugColors.LEGEND_TEXT)
      else:
        rl.draw_text_ex(self._font_normal, text,
                        rl.Vector2(x + 22, y - 2), font_size, 0, DebugColors.LEGEND_LABEL)
