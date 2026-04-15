const dashboardRoot = document.querySelector("#dashboard-root");
const tabList = document.querySelector("#tab-list");
const branchSwitcher = document.querySelector("#branch-switcher");
const sectionNav = document.querySelector("#section-nav");
const metaStrip = document.querySelector("#meta-strip");
const reportDateHighlight = document.querySelector("#report-date-highlight");
const dashboardTemplate = document.querySelector("#dashboard-template");
const sectionTemplate = document.querySelector("#section-template");
const chartModal = createChartModal();

const colors = {
  previousBarStroke: "#8da1b8",
  targetBar: "#d8dee6",
  actualBar: "#c20f2f",
  previousLine: "#b6c2d0",
  targetLine: "#8b95a1",
  actualLine: "#c20f2f",
};

const trendAxisConfig = {
  daily: {
    tickCount: 6,
    topPaddingRatio: 0.12,
    fallbackMax: 1000,
  },
  cumulative: {
    tickCount: 7,
    topPaddingRatio: 0.1,
    bottomPaddingRatio: 0.08,
    fallbackMax: 1000,
  },
};

const state = {
  payload: null,
  activeDashboard: "brief",
  activeAnchor: null,
  sectionObserver: null,
};

void loadDashboard();

async function loadDashboard() {
  try {
    const response = await fetch("./data/dashboard.json", { cache: "no-store" });
    if (!response.ok) {
      throw new Error(`加载 dashboard.json 失败，HTTP ${response.status}`);
    }

    const payload = await response.json();
    const dashboards = Object.values(payload.dashboards ?? {});
    if (!dashboards.length) {
      throw new Error("dashboard.json 中没有可渲染的页面数据。");
    }

    state.payload = payload;
    state.activeDashboard = payload.dashboards[state.activeDashboard] ? state.activeDashboard : dashboards[0].id;

    renderMeta(payload.meta ?? {});
    renderTabs(dashboards);
    renderDashboard(payload.dashboards[state.activeDashboard]);
  } catch (error) {
    renderError(error);
  }
}

function renderMeta(meta) {
  metaStrip.innerHTML = "";
  reportDateHighlight.innerHTML = `
    <span>报表日期</span>
    <strong>${escapeHtml(meta.reportDateLabel ?? "-")}</strong>
  `;

  [
    `数据范围：${meta.dataRangeStart ?? "-"} 至 ${meta.dataRangeEnd ?? "-"}`,
    `源数据更新时间：${formatDateTime(meta.workbookModifiedAt)}`,
  ].forEach((text) => {
    const item = document.createElement("span");
    item.className = "meta-text";
    item.textContent = text;
    metaStrip.appendChild(item);
  });
}

function renderTabs(dashboards) {
  tabList.innerHTML = "";
  dashboards.forEach((dashboard) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = dashboard.id === state.activeDashboard ? "active" : "";
    button.textContent = dashboard.title;
    button.addEventListener("click", () => {
      state.activeDashboard = dashboard.id;
      state.activeAnchor = null;
      renderTabs(dashboards);
      renderDashboard(dashboard);
      scrollToActiveDashboardTop();
    });
    tabList.appendChild(button);
  });
}

function scrollToActiveDashboardTop() {
  requestAnimationFrame(() => {
    const topTarget = dashboardRoot.firstElementChild ?? dashboardRoot;
    topTarget.scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

function renderDashboard(dashboard) {
  dashboardRoot.innerHTML = "";
  disconnectSectionObserver();
  if (branchSwitcher) {
    branchSwitcher.hidden = true;
  }
  if (sectionNav) {
    sectionNav.innerHTML = "";
  }

  if (!dashboard) {
    dashboardRoot.appendChild(renderEmptyBlock("当前页面不存在。"));
    return;
  }

  if (isBriefDashboard(dashboard)) {
    dashboardRoot.appendChild(renderBriefPage(dashboard));
    return;
  }

  const sections = dashboard.sections ?? [];
  if (!sections.length) {
    dashboardRoot.appendChild(renderEmptyBlock("当前 dashboard 暂无可展示数据。"));
    return;
  }

  const fragment = dashboardTemplate.content.cloneNode(true);
  const kickerNode = fragment.querySelector(".dashboard-kicker");
  const titleNode = fragment.querySelector(".dashboard-title");
  const headlineNode = fragment.querySelector(".dashboard-headline");
  kickerNode.textContent = dashboard.id.toUpperCase();
  titleNode.textContent = dashboard.title ?? "";
  headlineNode.textContent = dashboard.headline ?? "";
  if (!dashboard.headline) {
    headlineNode.remove();
    fragment.querySelector(".dashboard-header")?.classList.add("headline-hidden");
  }

  const sectionStack = fragment.querySelector(".section-stack");
  sections.forEach((section, index) => {
    sectionStack.appendChild(renderSection(section, dashboard.id, index));
  });

  dashboardRoot.appendChild(fragment);
  renderSectionDirectory();
}

function renderBriefPage(dashboard) {
  const briefing = dashboard.briefing ?? {};
  const sections = normalizeBriefSections(briefing).filter((section) => section.kind !== "intro");

  const article = document.createElement("article");
  article.className = "dashboard brief-page";
  article.innerHTML = `
    <header class="dashboard-header brief-page-header">
      <div>
        <p class="dashboard-kicker">Daily Brief</p>
        <h2 class="dashboard-title">${escapeHtml(dashboard.title ?? "")}</h2>
      </div>
      <div class="brief-page-meta">
        <p class="dashboard-headline">${escapeHtml(dashboard.headline ?? "")}</p>
      </div>
    </header>
  `;

  if (!dashboard.headline) {
    article.querySelector(".dashboard-headline")?.remove();
    article.querySelector(".brief-page-header")?.classList.add("headline-hidden");
  }

  if (!sections.length) {
    article.appendChild(renderEmptyBlock("每日简报暂无数据。"));
    return article;
  }

  const grid = document.createElement("div");
  grid.className = "brief-page-grid";
  sections.forEach((section, index) => {
    const card = document.createElement("article");
    card.className = "brief-page-card";
    if (section.kind) {
      card.classList.add(`kind-${String(section.kind).replace(/[^a-zA-Z0-9_-]+/g, "-")}`);
    }
    const anchorId = makeAnchorId(dashboard.id, section.kind ?? `section-${index}`);
    card.id = anchorId;
    card.dataset.anchorId = anchorId;
    card.dataset.navAnchor = "true";
    card.dataset.navLabel = section.title ?? `板块 ${index + 1}`;
    if (section.kind === "arrival") {
      card.classList.add("arrival-brief");
    }

    const title = document.createElement("h3");
    title.className = "brief-page-card-title";
    title.textContent = section.title ?? "";
    card.appendChild(title);

    (section.lines ?? []).forEach((line) => {
      const paragraph = document.createElement("p");
      paragraph.className = "brief-page-line";
      paragraph.innerHTML = formatBriefLine(line);
      card.appendChild(paragraph);
    });

    grid.appendChild(card);
  });

  article.appendChild(grid);
  return article;
}

function renderSectionDirectory() {
  if (!branchSwitcher || !sectionNav) {
    return;
  }

  const anchors = [...dashboardRoot.querySelectorAll("[data-nav-anchor='true']")]
    .map((node) => ({
      id: node.dataset.anchorId,
      label: node.dataset.navLabel,
      node,
    }))
    .filter((item) => item.id && item.label);

  sectionNav.innerHTML = "";
  disconnectSectionObserver();

  if (anchors.length < 2) {
    branchSwitcher.hidden = true;
    return;
  }

  branchSwitcher.hidden = false;
  anchors.forEach((item, index) => {
    const link = document.createElement("a");
    link.href = `#${item.id}`;
    link.className = "section-nav-link";
    link.dataset.anchorTarget = item.id;
    link.innerHTML = `
      <span class="section-nav-index">${String(index + 1).padStart(2, "0")}</span>
      <span class="section-nav-label">${escapeHtml(item.label)}</span>
    `;
    link.addEventListener("click", (event) => {
      event.preventDefault();
      state.activeAnchor = item.id;
      updateSectionDirectoryState(item.id);
      item.node.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    sectionNav.appendChild(link);
  });

  setupSectionObserver(anchors);
  updateSectionDirectoryState(state.activeAnchor ?? anchors[0].id);
}

function setupSectionObserver(anchors) {
  if (!anchors.length) {
    return;
  }

  state.sectionObserver = new IntersectionObserver(
    (entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];

      if (visible?.target instanceof HTMLElement) {
        const id = visible.target.dataset.anchorId;
        if (id) {
          state.activeAnchor = id;
          updateSectionDirectoryState(id);
        }
      }
    },
    {
      root: null,
      rootMargin: "-12% 0px -68% 0px",
      threshold: [0.2, 0.35, 0.55, 0.75],
    },
  );

  anchors.forEach((item) => {
    state.sectionObserver?.observe(item.node);
  });
}

function disconnectSectionObserver() {
  state.sectionObserver?.disconnect();
  state.sectionObserver = null;
}

function updateSectionDirectoryState(activeId) {
  [...sectionNav.querySelectorAll(".section-nav-link")].forEach((link) => {
    link.classList.toggle("active", link.dataset.anchorTarget === activeId);
  });
}

function getSectionNavLabel(section) {
  return section.title || section.navLabel || section.sectionLabel || prettifySectionId(section.id) || "";
}

function isBriefDashboard(dashboard) {
  return dashboard?.pageType === "brief" || dashboard?.id === "brief" || Boolean(dashboard?.briefing);
}

function formatBriefLine(line) {
  const escaped = escapeHtml(line);
  const placeholders = [];
  const protectedLine = escaped.replace(/(\d+\s*-\s*\d+(?:日)?)/g, (match) => {
    const token = `__RANGE_${String.fromCharCode(65 + placeholders.length)}__`;
    placeholders.push(match);
    return token;
  });

  const highlighted = protectedLine.replace(/(?<![A-Za-z])(-?\d[\d,]*(?:\.\d+)?%?)(?![A-Za-z])/g, (match) => {
    const className = match.startsWith("-") ? "brief-number is-negative" : "brief-number";
    const leadingSpace = match.startsWith("-") ? "" : " ";
    return `${leadingSpace}<span class="${className}">${match}</span>`;
  });

  return placeholders.reduce(
    (text, item, index) => text.replace(`__RANGE_${String.fromCharCode(65 + index)}__`, item),
    highlighted,
  );
}

function normalizeBriefSections(briefing) {
  if (Array.isArray(briefing?.sections) && briefing.sections.length) {
    return briefing.sections;
  }

  const generatedText = briefing?.generatedText;
  if (!generatedText) {
    return [];
  }

  return String(generatedText)
    .split(/\n\s*\n/)
    .map((block) => block.trim())
    .filter(Boolean)
    .map((block, index) => {
      const lines = block.split("\n").map((line) => line.trim()).filter(Boolean);
      const titleMatch = lines[0]?.match(/^【(.+?)】$/);
      if (index === 0 && !titleMatch) {
        return { kind: "intro", title: "开场", lines };
      }
      return {
        kind: `section-${index}`,
        title: titleMatch ? titleMatch[1] : `简报内容 ${index + 1}`,
        lines: titleMatch ? lines.slice(1) : lines,
      };
    });
}

function renderSection(section, dashboardId, index) {
  const fragment = sectionTemplate.content.cloneNode(true);
  const labelNode = fragment.querySelector(".section-label");
  const titleNode = fragment.querySelector(".section-title");
  const headlineNode = fragment.querySelector(".section-headline");
  const titleBlock = labelNode.parentElement;
  const sectionLabel = section.sectionLabel ?? (section.id ?? "").replaceAll("-", " ");
  const sectionTitle = section.title ?? "";

  labelNode.textContent = sectionLabel;
  titleNode.textContent = sectionTitle;
  headlineNode.textContent = section.headline ?? "";

  if (!sectionLabel && !sectionTitle) {
    titleBlock.remove();
    fragment.querySelector(".section-topline")?.classList.add("is-headline-only");
  }
  if (!section.headline) {
    headlineNode.remove();
    fragment.querySelector(".section-topline")?.classList.add("headline-hidden");
  }
  fragment.querySelector(".summary-panel")?.remove();

  const noteNode = fragment.querySelector(".section-note");
  if (section.note) {
    noteNode.textContent = section.note;
    if (section.noteHasError) {
      noteNode.classList.add("error");
    }
  } else {
    noteNode.remove();
  }

  const headers = fragment.querySelectorAll(".chart-header");
  headers[0].querySelector("h4").textContent = section.trend?.chartTitle ?? "月度趋势";
  headers[1].querySelector("h4").textContent = section.trend?.tableTitle ?? "月度对照表";

  headers[0].querySelector("p")?.remove();
  headers[1].querySelector("p")?.remove();

  const chartNode = renderTrendChart(section.trend);
  chartNode.classList.add("clickable-chart");
  chartNode.addEventListener("click", () => openChartModal(section));
  fragment.querySelector(".chart-wrap").appendChild(chartNode);
  fragment.querySelector(".table-wrap").appendChild(renderTrendBoard(section.trend));

  const container = document.createElement("div");
  container.appendChild(fragment);
  const node = container.firstElementChild;
  const anchorId = makeAnchorId(dashboardId, section.id ?? `section-${index + 1}`);
  node.id = anchorId;
  node.dataset.anchorId = anchorId;
  node.dataset.navAnchor = "true";
  node.dataset.navLabel = getSectionNavLabel(section);
  if (isArrivalTrend(section.trend)) {
    node.classList.add("arrival-section");
  }
  return node;
}

function renderMetricCard(card) {
  const node = document.createElement("article");
  node.className = "metric-card";
  node.innerHTML = `
    <label>${escapeHtml(card.label ?? "")}</label>
    <strong>${escapeHtml(card.displayValue ?? "-")}</strong>
    ${card.note ? `<p class="card-note">${escapeHtml(card.note)}</p>` : ""}
  `;
  return node;
}

function renderTrendBoard(trend) {
  if (!trend?.matrix?.rows?.length) {
    return renderEmptyBlock("当前没有可渲染的月度对照数据。");
  }

  const isArrival = isArrivalTrend(trend);
  const board = document.createElement("div");
  board.className = "trend-board";
  if (isArrival) {
    board.classList.add("arrival-board");
  }

  const summary = document.createElement("div");
  summary.className = "trend-summary";
  (trend.summary?.items ?? []).forEach((item) => {
    const article = document.createElement("article");
    article.className = "trend-summary-item";
    const valueClass = getSummaryValueClass(item);
    article.innerHTML = `
      <label>${escapeHtml(item.label ?? "")}</label>
      <strong class="${valueClass}">${escapeHtml(item.displayValue ?? "-")}</strong>
      ${item.note ? `<p>${formatSummaryNote(item.note)}</p>` : ""}
    `;
    summary.appendChild(article);
  });

  const matrixWrap = document.createElement("div");
  matrixWrap.className = "trend-matrix-wrap";
  const table = document.createElement("table");
  table.className = "trend-matrix";
  if (isArrival) {
    table.classList.add("arrival-matrix");
  }
  const columnMeta = trend.matrix.columnMeta ?? [];

  const defaultVisibleRowKeys = ["previousActual", "target", "actual", "dayDelta"];
  const hasDeclaredVisibleRowKeys = Array.isArray(trend.matrix.visibleRowKeys) && trend.matrix.visibleRowKeys.length;
  const declaredVisibleRowKeys = hasDeclaredVisibleRowKeys ? trend.matrix.visibleRowKeys : defaultVisibleRowKeys;
  const visibleRows = hasDeclaredVisibleRowKeys
    ? (trend.matrix.rows ?? []).filter((row) => declaredVisibleRowKeys.includes(row.key))
    : isArrival
      ? trend.matrix.rows ?? []
      : (trend.matrix.rows ?? []).filter((row) => declaredVisibleRowKeys.includes(row.key));

  const getTrendCellClassName = (rowKey, meta = {}) => {
    const classNames = [];
    const shouldHighlightPrevious = rowKey === "previousActual" && meta.highlightPrevious;
    const shouldHighlightCurrent = ["target", "actual", "nevActual", "iceActual"].includes(rowKey) && meta.highlightCurrent;

    if (shouldHighlightPrevious || shouldHighlightCurrent) {
      classNames.push("is-calendar-highlight");
    }
    if (shouldHighlightCurrent) classNames.push("is-current-highlight");
    if (shouldHighlightPrevious) classNames.push("is-previous-highlight");
    if ((shouldHighlightCurrent && meta.isCurrentHoliday) || (shouldHighlightPrevious && meta.isPreviousHoliday)) {
      classNames.push("is-holiday-highlight");
    }
    return classNames.join(" ");
  };

  const getTrendCellHint = (rowKey, meta = {}) => {
    if (rowKey === "previousActual") {
      if (meta.isPreviousHoliday) return "上期节假日";
      if (meta.isPreviousWeekend) return "上期周末";
      return "";
    }
    if (["target", "actual"].includes(rowKey)) {
      if (meta.isCurrentHoliday) return "本期节假日";
      if (meta.isCurrentWeekend) return "本期周末";
    }
    if (["nevActual", "iceActual"].includes(rowKey)) {
      if (meta.isCurrentHoliday) return "本期节假日";
      if (meta.isCurrentWeekend) return "本期周末";
    }
    return "";
  };

  const getTrendValueClassName = (row, value) => {
    const classNames = [];
    const rowKey = row?.key ?? "";
    const rowLabel = row?.label ?? "";
    const text = String(value ?? "").trim();

    if (["actual", "nevActual", "iceActual"].includes(rowKey)) {
      classNames.push("is-accent-value");
    }
    if (rowKey === "target") {
      classNames.push("is-target-value");
    }
    if (isRatioMetric(rowKey, rowLabel)) {
      classNames.push("is-ratio-value");
      const directionClass = getMetricDirectionClass(null, text);
      if (directionClass) classNames.push(directionClass);
    }
    return classNames.join(" ");
  };

  const headerCells = (trend.matrix.labels ?? [])
    .map((label) => `<th>${escapeHtml(label)}</th>`)
    .join("");

  table.innerHTML = `
    <thead>
      <tr>
        <th>${escapeHtml(trend.matrix.stubLabel ?? "维度")}</th>
        ${headerCells}
      </tr>
    </thead>
    <tbody>
      ${visibleRows
        .map(
          (row) => `
            <tr class="trend-row trend-row-${escapeHtml(row.key ?? "default")}">
              <th>${escapeHtml(row.label ?? "")}</th>
              ${(row.displayValues ?? [])
                .map((value, index) => {
                  const meta = columnMeta[index] ?? {};
                  const className = [getTrendCellClassName(row.key, meta), getTrendValueClassName(row, value)]
                    .filter(Boolean)
                    .join(" ");
                  const title = getTrendCellHint(row.key, meta);
                  return `<td class="${className}"${title ? ` title="${escapeHtml(title)}"` : ""}>${escapeHtml(value ?? "-")}</td>`;
                })
                .join("")}
            </tr>
          `,
        )
        .join("")}
    </tbody>
  `;

  matrixWrap.appendChild(table);
  board.appendChild(summary);
  board.appendChild(matrixWrap);
  return board;
}

function renderTrendChart(trend, options = {}) {
  const chart = trend?.chart;
  if (!chart?.labels?.length) {
    return renderEmptyBlock("当前没有可绘制的趋势图数据。");
  }

  const wrapper = document.createElement("div");
  wrapper.className = "mixed-chart";
  const viewport = getTrendChartViewport(chart, options);
  if (options.enlarged) {
    wrapper.classList.add("is-enlarged");
  }
  if (viewport.compact) {
    wrapper.classList.add("is-compact");
  }
  if (viewport.scrollWidth) {
    wrapper.style.minWidth = `${viewport.scrollWidth}px`;
  }

  if (!options.enlarged) {
    const hint = document.createElement("span");
    hint.className = "chart-zoom-hint";
    hint.textContent = "点击放大查看";
    wrapper.appendChild(hint);
  }

  const tooltip = document.createElement("div");
  tooltip.className = "chart-tooltip";
  wrapper.appendChild(tooltip);

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  const { width, height, padding } = viewport;
  const minX = padding.left;
  const maxX = width - padding.right;
  const minY = padding.top;
  const maxY = height - padding.bottom;
  const plotHeight = maxY - minY;
  const bandWidth = (maxX - minX) / Math.max(chart.labels.length, 1);
  const defs = getSeriesDefinitions(chart);
  const visibleSeriesKeys = new Set(defs.map((item) => item.key));
  const dailyAxis = buildDailyAxis(chart);
  const cumulativeAxis = buildCumulativeAxis(chart, defs);

  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);

  dailyAxis.ticks.forEach((value) => {
    const y = scaleDaily(value, dailyAxis, minY, maxY);
    svg.appendChild(createLine(minX, y, maxX, y, { stroke: "rgba(20,34,31,0.12)", "stroke-width": "1.5" }));
    svg.appendChild(
      createText(minX - 12, y + 5, formatTick(value), {
        "text-anchor": "end",
        fill: "rgba(20,34,31,0.65)",
        "font-size": viewport.axisFontSize,
      }),
    );
  });

  cumulativeAxis.ticks.forEach((value) => {
    const y = scaleCumulative(value, cumulativeAxis, minY, maxY);
    svg.appendChild(
      createText(maxX + 18, y + 5, formatTick(value), {
        "text-anchor": "start",
        fill: "rgba(20,34,31,0.65)",
        "font-size": viewport.axisFontSize,
      }),
    );
  });

  chart.labels.forEach((label, index) => {
    const centerX = getBandCenter(index, bandWidth, minX);
    const targetWidth = bandWidth * 0.42;
    const sideWidth = bandWidth * 0.18;

    if (visibleSeriesKeys.has("target")) {
      drawBar(svg, centerX, chart.series?.target?.[index], dailyAxis, minY, maxY, targetWidth, {
        fill: colors.targetBar,
        opacity: "0.9",
      });
    }
    if (visibleSeriesKeys.has("previousActual")) {
      drawBar(svg, centerX - bandWidth * 0.18, chart.series?.previousActual?.[index], dailyAxis, minY, maxY, sideWidth, {
        fill: "rgba(255,255,255,0.85)",
        stroke: colors.previousBarStroke,
        "stroke-width": "1.4",
      });
    }
    if (visibleSeriesKeys.has("actual")) {
      drawBar(svg, centerX + bandWidth * 0.18, chart.series?.actual?.[index], dailyAxis, minY, maxY, sideWidth, {
        fill: colors.actualBar,
      });
    }

    const actualValue = chart.series?.actual?.[index];
    if (typeof actualValue === "number" && Number.isFinite(actualValue)) {
      const y = scaleDaily(actualValue, dailyAxis, minY, maxY) - 8;
      svg.appendChild(
        createText(centerX + bandWidth * 0.18, Math.max(y, minY + 12), formatCompact(actualValue), {
          "text-anchor": "middle",
          fill: "rgba(20,34,31,0.72)",
          "font-size": viewport.valueFontSize,
        }),
      );
    }

    svg.appendChild(
      createText(centerX, height - 28, label, {
        "text-anchor": "middle",
        fill: "rgba(20,34,31,0.68)",
        "font-size": viewport.labelFontSize,
      }),
    );
  });

  const lineSeries = defs.filter((item) => item.type === "line");
  lineSeries.forEach((item) => {
    const points = buildLinePoints(chart.series?.[item.key] ?? [], cumulativeAxis, minX, bandWidth, minY, maxY);
    if (!points.some((point) => point !== null)) {
      return;
    }

    const path = document.createElementNS(svg.namespaceURI, "path");
    path.setAttribute("d", buildLinePath(points));
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", item.color);
    path.setAttribute("stroke-width", item.strokeWidth);
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");
    if (item.dashed) {
      path.setAttribute("stroke-dasharray", "8 6");
    }
    svg.appendChild(path);

    points.forEach((point) => {
      if (!point || !item.markers) {
        return;
      }
      const circle = document.createElementNS(svg.namespaceURI, "circle");
      circle.setAttribute("cx", point.x);
      circle.setAttribute("cy", point.y);
      circle.setAttribute("r", item.markerRadius ?? 4.5);
      circle.setAttribute("fill", item.markerFill ?? item.color);
      circle.setAttribute("stroke", item.markerStroke ?? "#ffffff");
      circle.setAttribute("stroke-width", viewport.markerStrokeWidth);
      svg.appendChild(circle);
    });
  });

  chart.labels.forEach((_, index) => {
    const band = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    band.setAttribute("x", String(minX + index * bandWidth));
    band.setAttribute("y", String(minY));
    band.setAttribute("width", String(bandWidth));
    band.setAttribute("height", String(plotHeight));
    band.setAttribute("fill", "transparent");
    band.classList.add("hover-band");
    band.addEventListener("mouseenter", (event) => showTooltip(event, tooltip, chart, index));
    band.addEventListener("mousemove", (event) => moveTooltip(event, tooltip));
    band.addEventListener("mouseleave", () => hideTooltip(tooltip));
    svg.appendChild(band);
  });

  wrapper.appendChild(svg);

  const legend = document.createElement("div");
  legend.className = "legend legend-wide";
  defs.forEach((item) => {
    const legendItem = document.createElement("span");
    legendItem.className = `legend-item ${hasNumericValues(chart.series?.[item.key]) ? "" : "muted"}`.trim();
    const swatchStyle = getLegendSwatchStyle(item);
    legendItem.innerHTML = `<span class="legend-swatch ${item.type === "line" ? `line${item.dashed ? " is-dashed" : ""}` : "bar"}" style="${swatchStyle}"></span><span>${escapeHtml(item.label)}</span>`;
    legend.appendChild(legendItem);
  });
  wrapper.appendChild(legend);

  if (chart.note) {
    const note = document.createElement("p");
    note.className = "chart-caption";
    note.textContent = chart.note;
    wrapper.appendChild(note);
  }

  return wrapper;
}

function createChartModal() {
  const modal = document.createElement("div");
  modal.className = "chart-modal";
  modal.innerHTML = `
    <div class="chart-modal-backdrop" data-close-modal="true"></div>
    <div class="chart-modal-dialog" role="dialog" aria-modal="true" aria-label="放大趋势图">
      <button type="button" class="chart-modal-close" aria-label="关闭">×</button>
      <div class="chart-modal-meta">
        <p class="chart-modal-kicker">Chart Zoom</p>
        <h3 class="chart-modal-title"></h3>
        <p class="chart-modal-subtitle"></p>
      </div>
      <div class="chart-modal-content"></div>
    </div>
  `;

  modal.addEventListener("click", (event) => {
    if (event.target instanceof HTMLElement && event.target.dataset.closeModal === "true") {
      closeChartModal();
    }
    if (event.target instanceof HTMLElement && event.target.classList.contains("chart-modal-close")) {
      closeChartModal();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && modal.classList.contains("visible")) {
      closeChartModal();
    }
  });

  document.body.appendChild(modal);
  return modal;
}

function openChartModal(section) {
  const content = chartModal.querySelector(".chart-modal-content");
  const title = chartModal.querySelector(".chart-modal-title");
  const subtitle = chartModal.querySelector(".chart-modal-subtitle");
  const compact = isCompactChartViewport();
  content.innerHTML = "";
  title.textContent = section.title ? `${section.title} 趋势图` : section.trend?.chartTitle ?? "趋势图";
  subtitle.textContent = compact
    ? `${section.trend?.chartTitle ?? section.headline ?? ""} · 左右滑动查看`
    : section.trend?.chartTitle ?? section.headline ?? "";
  content.appendChild(renderTrendChart(section.trend, { enlarged: true }));
  chartModal.classList.toggle("is-compact", compact);
  chartModal.classList.add("visible");
  document.body.classList.add("modal-open");
}

function closeChartModal() {
  chartModal.classList.remove("visible");
  chartModal.classList.remove("is-compact");
  document.body.classList.remove("modal-open");
}

function getSeriesDefinitions(chart) {
  const hiddenSeriesKeys = new Set(Array.isArray(chart?.hiddenSeriesKeys) ? chart.hiddenSeriesKeys : []);
  if (Array.isArray(chart?.seriesDefinitions) && chart.seriesDefinitions.length) {
    return chart.seriesDefinitions.filter((item) => !hiddenSeriesKeys.has(item.key));
  }
  return [
    {
      key: "previousActual",
      label: "上期实绩",
      type: "bar",
      color: colors.previousBarStroke,
      fill: "rgba(255,255,255,0.85)",
      stroke: colors.previousBarStroke,
      strokeWidth: 1.4,
    },
    { key: "target", label: "本期目标", type: "bar", color: colors.targetBar, fill: colors.targetBar, opacity: 0.9 },
    { key: "actual", label: "本期实绩", type: "bar", color: colors.actualBar, fill: colors.actualBar },
    { key: "cumulativeTarget", label: "本期累计目标", type: "line", color: colors.targetLine, dashed: true, strokeWidth: "3" },
    {
      key: "cumulativeActual",
      label: "本期累计实绩",
      type: "line",
      color: colors.actualLine,
      strokeWidth: "3.5",
      markers: true,
      markerFill: "#ffffff",
      markerStroke: colors.actualLine,
      markerRadius: 4.8,
    },
    {
      key: "previousCumulative",
      label: "上期累计实绩",
      type: "line",
      color: colors.previousLine,
      strokeWidth: "3",
      markers: false,
    },
  ].filter((item) => !hiddenSeriesKeys.has(item.key));
}

function buildDailyAxis(chart) {
  const hiddenSeriesKeys = new Set(Array.isArray(chart?.hiddenSeriesKeys) ? chart.hiddenSeriesKeys : []);
  const dailyKeys = ["previousActual", "target", "actual"].filter((key) => !hiddenSeriesKeys.has(key));
  return buildAdaptiveAxis(collectNumericSeriesValues(chart, dailyKeys), {
    forceMinZero: true,
    tickCount: trendAxisConfig.daily.tickCount,
    topPaddingRatio: trendAxisConfig.daily.topPaddingRatio,
    fallbackMax: trendAxisConfig.daily.fallbackMax,
  });
}

function buildCumulativeAxis(chart, defs) {
  const lineKeys = defs.filter((item) => item.type === "line").map((item) => item.key);
  return buildAdaptiveAxis(collectNumericSeriesValues(chart, lineKeys), {
    tickCount: trendAxisConfig.cumulative.tickCount,
    topPaddingRatio: trendAxisConfig.cumulative.topPaddingRatio,
    bottomPaddingRatio: trendAxisConfig.cumulative.bottomPaddingRatio,
    fallbackMax: trendAxisConfig.cumulative.fallbackMax,
  });
}

function collectNumericSeriesValues(chart, keys) {
  return keys.flatMap((key) =>
    (chart?.series?.[key] ?? []).filter((value) => typeof value === "number" && Number.isFinite(value)),
  );
}

function buildAdaptiveAxis(values, options = {}) {
  const numericValues = values.filter((value) => typeof value === "number" && Number.isFinite(value));
  const forceMinZero = Boolean(options.forceMinZero);
  const tickCount = Math.max(options.tickCount ?? 5, 2);
  const fallbackMax = Math.max(options.fallbackMax ?? 1, 1);
  const topPaddingRatio = Math.max(options.topPaddingRatio ?? 0.1, 0);
  const bottomPaddingRatio = forceMinZero ? 0 : Math.max(options.bottomPaddingRatio ?? 0.06, 0);

  if (!numericValues.length) {
    return buildAxisFromBounds(0, fallbackMax, tickCount, forceMinZero);
  }

  const rawMin = Math.min(...numericValues);
  const rawMax = Math.max(...numericValues);

  if (rawMin === rawMax) {
    const base = Math.max(Math.abs(rawMax), fallbackMax);
    let singleMin = forceMinZero ? 0 : rawMin - base * Math.max(bottomPaddingRatio, 0.08);
    let singleMax = rawMax + base * Math.max(topPaddingRatio, 0.12);
    if (!forceMinZero && rawMin >= 0) {
      singleMin = Math.max(singleMin, 0);
    }
    if (!forceMinZero && rawMax <= 0) {
      singleMax = Math.min(singleMax, 0);
    }
    return buildAxisFromBounds(singleMin, singleMax, tickCount, forceMinZero);
  }

  const span = rawMax - rawMin;
  let minValue = forceMinZero ? 0 : rawMin - span * bottomPaddingRatio;
  let maxValue = rawMax + span * topPaddingRatio;
  if (!forceMinZero && rawMin >= 0) {
    minValue = Math.max(minValue, 0);
  }
  if (!forceMinZero && rawMax <= 0) {
    maxValue = Math.min(maxValue, 0);
  }
  return buildAxisFromBounds(minValue, maxValue, tickCount, forceMinZero);
}

function buildAxisFromBounds(minValue, maxValue, tickCount, forceMinZero) {
  const safeMin = Number.isFinite(minValue) ? minValue : 0;
  const safeMax = Number.isFinite(maxValue) ? maxValue : 1;
  const normalizedMin = forceMinZero ? 0 : Math.min(safeMin, safeMax);
  const normalizedMax = Math.max(safeMax, normalizedMin + 1);
  const step = getNiceStep(normalizedMin, normalizedMax, tickCount);
  const axisMin = forceMinZero ? 0 : Math.floor(normalizedMin / step) * step;
  const axisMax = Math.max(Math.ceil(normalizedMax / step) * step, axisMin + step);
  const ticks = [];

  for (let value = axisMin; value <= axisMax + step * 0.5; value += step) {
    ticks.push(normalizeAxisValue(value));
  }

  return {
    min: normalizeAxisValue(axisMin),
    max: normalizeAxisValue(axisMax),
    ticks,
  };
}

function getNiceStep(minValue, maxValue, tickCount) {
  const span = Math.max(Math.abs(maxValue - minValue), 1);
  const roughStep = span / Math.max(tickCount - 1, 1);
  return niceNumber(roughStep, true);
}

function niceNumber(value, round) {
  const safeValue = Math.max(Math.abs(value), 1);
  const exponent = Math.floor(Math.log10(safeValue));
  const fraction = safeValue / 10 ** exponent;
  let niceFraction;

  if (round) {
    if (fraction < 1.5) {
      niceFraction = 1;
    } else if (fraction < 2.25) {
      niceFraction = 2;
    } else if (fraction < 3.75) {
      niceFraction = 2.5;
    } else if (fraction < 7.5) {
      niceFraction = 5;
    } else {
      niceFraction = 10;
    }
  } else if (fraction <= 1) {
    niceFraction = 1;
  } else if (fraction <= 2) {
    niceFraction = 2;
  } else if (fraction <= 2.5) {
    niceFraction = 2.5;
  } else if (fraction <= 5) {
    niceFraction = 5;
  } else {
    niceFraction = 10;
  }

  return niceFraction * 10 ** exponent;
}

function normalizeAxisValue(value) {
  return Number(value.toFixed(6));
}

function drawBar(svg, centerX, value, axis, minY, maxY, width, attrs) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return;
  }
  const y = scaleDaily(value, axis, minY, maxY);
  const rect = document.createElementNS(svg.namespaceURI, "rect");
  rect.setAttribute("x", String(centerX - width / 2));
  rect.setAttribute("y", String(y));
  rect.setAttribute("width", String(width));
  rect.setAttribute("height", String(Math.max(maxY - y, 0.8)));
  Object.entries(attrs).forEach(([key, attrValue]) => rect.setAttribute(key, attrValue));
  svg.appendChild(rect);
}

function buildLinePoints(values, axis, minX, bandWidth, minY, maxY) {
  return values.map((value, index) => {
    if (typeof value !== "number" || !Number.isFinite(value)) {
      return null;
    }
    return {
      x: getBandCenter(index, bandWidth, minX),
      y: scaleCumulative(value, axis, minY, maxY),
    };
  });
}

function buildLinePath(points) {
  let path = "";
  let started = false;
  points.forEach((point) => {
    if (!point) {
      started = false;
      return;
    }
    path += `${started ? " L" : "M"} ${point.x} ${point.y}`;
    started = true;
  });
  return path.trim();
}

function showTooltip(event, tooltip, chart, index) {
  const defs = getSeriesDefinitions(chart);
  const rows = defs
    .map((item) => {
      const value = chart.series?.[item.key]?.[index];
      const dotStyle = getTooltipDotStyle(item);
      return `
        <div class="chart-tooltip-row">
          <span class="tooltip-series">
            <span class="tooltip-dot" style="${dotStyle}"></span>
            ${escapeHtml(item.label)}
          </span>
          <strong>${escapeHtml(formatTooltipValue(value))}</strong>
        </div>
      `;
    })
    .join("");

  tooltip.innerHTML = `
    <div class="tooltip-date">${escapeHtml(chart.labels?.[index] ?? "-")}</div>
    ${rows}
  `;
  tooltip.classList.add("visible");
  moveTooltip(event, tooltip);
}

function moveTooltip(event, tooltip) {
  const frame = tooltip.parentElement.getBoundingClientRect();
  tooltip.style.left = `${event.clientX - frame.left + 12}px`;
  tooltip.style.top = `${event.clientY - frame.top - 16}px`;
}

function hideTooltip(tooltip) {
  tooltip.classList.remove("visible");
}

function getTrendChartViewport(chart, options = {}) {
  const compact = Boolean(options.enlarged && isCompactChartViewport());
  const labelCount = Math.max(chart?.labels?.length ?? 0, 1);

  if (compact) {
    const width = Math.max(1080, labelCount * 52 + 280);
    return {
      compact: true,
      width,
      height: 640,
      padding: { top: 36, right: 88, bottom: 100, left: 72 },
      axisFontSize: "14",
      valueFontSize: "12",
      labelFontSize: "13",
      markerStrokeWidth: "2",
      scrollWidth: width,
    };
  }

  if (options.enlarged) {
    return {
      compact: false,
      width: 1920,
      height: 760,
      padding: { top: 44, right: 112, bottom: 108, left: 88 },
      axisFontSize: "18",
      valueFontSize: "16",
      labelFontSize: "16",
      markerStrokeWidth: "2.5",
      scrollWidth: 0,
    };
  }

  return {
    compact: false,
    width: 1560,
    height: 620,
    padding: { top: 40, right: 90, bottom: 92, left: 72 },
    axisFontSize: "14",
    valueFontSize: "12",
    labelFontSize: "13",
    markerStrokeWidth: "2",
    scrollWidth: 0,
  };
}

function isCompactChartViewport() {
  return typeof window !== "undefined" && window.matchMedia("(max-width: 980px)").matches;
}

function getBandCenter(index, bandWidth, minX) {
  return minX + index * bandWidth + bandWidth / 2;
}

function scaleDaily(value, axis, minY, maxY) {
  return scaleChartValue(value, axis.min, axis.max, minY, maxY);
}

function scaleCumulative(value, axis, minY, maxY) {
  return scaleChartValue(value, axis.min, axis.max, minY, maxY);
}

function scaleChartValue(value, axisMin, axisMax, minY, maxY) {
  const safeMin = Number.isFinite(axisMin) ? axisMin : 0;
  const safeMax = Number.isFinite(axisMax) ? axisMax : 1;
  const domain = Math.max(safeMax - safeMin, 1);
  const clampedValue = Math.min(Math.max(value, safeMin), safeMax);
  return maxY - ((clampedValue - safeMin) / domain) * (maxY - minY);
}

function createLine(x1, y1, x2, y2, attrs) {
  const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
  line.setAttribute("x1", x1);
  line.setAttribute("y1", y1);
  line.setAttribute("x2", x2);
  line.setAttribute("y2", y2);
  Object.entries(attrs).forEach(([key, value]) => line.setAttribute(key, value));
  return line;
}

function createText(x, y, text, attrs) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", "text");
  node.setAttribute("x", x);
  node.setAttribute("y", y);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
  node.textContent = text;
  return node;
}

function renderError(error) {
  const message = error instanceof Error ? error.message : String(error);
  disconnectSectionObserver();
  if (branchSwitcher) {
    branchSwitcher.hidden = true;
  }
  metaStrip.innerHTML = "";
  dashboardRoot.innerHTML = "";
  dashboardRoot.appendChild(renderEmptyBlock(`页面加载失败：${message}`));
}

function renderEmptyBlock(message) {
  const block = document.createElement("div");
  block.className = "metric-card empty-card";
  block.innerHTML = `<strong>${escapeHtml(message)}</strong>`;
  return block;
}

function hasNumericValues(values) {
  return Array.isArray(values) && values.some((value) => typeof value === "number" && Number.isFinite(value));
}

function formatDateTime(value) {
  return value ? value.replace("T", " ") : "-";
}

function formatTooltipValue(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  return new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 }).format(value);
}

function formatTick(value) {
  const numericValue = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(numericValue)) {
    return "-";
  }

  const absValue = Math.abs(numericValue);
  if (absValue >= 1000000) {
    return `${formatTickNumber(numericValue / 1000000)}m`;
  }
  if (absValue >= 1000) {
    return `${formatTickNumber(numericValue / 1000)}k`;
  }
  return formatTickNumber(numericValue);
}

function formatTickNumber(value) {
  const absValue = Math.abs(value);
  const digits = absValue >= 100 ? 0 : absValue >= 10 ? 1 : 2;
  return Number(value.toFixed(digits)).toString();
}

function formatCompact(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    return "-";
  }
  return Math.round(value).toString();
}

function getSummaryValueClass(item) {
  const classes = [];
  if (!isRatioMetric("", item?.label ?? "")) {
    return classes.join(" ");
  }

  const numericValue = typeof item?.value === "number" ? item.value : null;
  const displayValue = typeof item?.displayValue === "string" ? item.displayValue.trim() : "";
  const directionClass = getMetricDirectionClass(numericValue, displayValue);
  if (directionClass) classes.push(directionClass);

  return classes.join(" ");
}

function formatSummaryNote(note) {
  const text = String(note ?? "");
  if (!isRatioMetric("", text)) {
    return escapeHtml(text);
  }

  const escaped = escapeHtml(text);
  return escaped.replace(/(?<![A-Za-z])(-?\d[\d,]*(?:\.\d+)?%?)(?![A-Za-z])/g, (match) => {
    if (match === "-") {
      return match;
    }
    const className = getMetricDirectionClass(null, match);
    return className ? `<span class="${className}">${match}</span>` : match;
  });
}

function isRatioMetric(key, label) {
  const keyText = String(key ?? "").toLowerCase();
  const labelText = String(label ?? "");
  return /同比|环比/.test(labelText) || keyText.includes("delta") || keyText.includes("ratio");
}

function getMetricDirectionClass(value, displayValue) {
  const numericValue = typeof value === "number" && Number.isFinite(value) ? value : parseMetricValue(displayValue);
  if (numericValue === null || numericValue === 0) {
    return "";
  }
  return numericValue < 0 ? "is-negative-value" : "is-positive-value";
}

function parseMetricValue(displayValue) {
  const text = String(displayValue ?? "").trim();
  if (!text || text === "-") {
    return null;
  }
  const normalized = text.replace(/,/g, "").replace(/%$/, "");
  const parsed = Number(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function getTooltipDotStyle(item) {
  if (item.key === "previousActual") {
    return `background: rgba(255,255,255,0.96); border: 2px solid ${item.stroke ?? item.color};`;
  }

  return `background: ${item.color}; border: 2px solid ${item.color};`;
}

function getLegendSwatchStyle(item) {
  if (item.type === "line") {
    return `--swatch:${item.color}; --swatch-accent:${item.accent ?? item.color};`;
  }

  return [
    `--swatch:${item.color}`,
    `--swatch-accent:${item.accent ?? item.color}`,
    `--swatch-fill:${item.fill ?? item.color}`,
    `--swatch-border:${item.stroke ?? item.accent ?? item.color}`,
    `--swatch-border-width:${item.strokeWidth ?? 1.5}px`,
  ].join("; ");
}

function isArrivalTrend(trend) {
  return trend?.viewType === "arrival" || (trend?.matrix?.rows ?? []).some((row) => ["nevActual", "iceActual", "iceDelta"].includes(row.key));
}

function makeAnchorId(...parts) {
  const text = parts
    .filter(Boolean)
    .join("-")
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  return text || `section-${Date.now()}`;
}

function prettifySectionId(value) {
  return String(value ?? "")
    .replaceAll("-", " ")
    .trim();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}
