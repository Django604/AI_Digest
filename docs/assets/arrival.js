const reportDateHighlight = document.querySelector('#report-date-highlight');
const metaStrip = document.querySelector('#meta-strip');
const dashboardHeadline = document.querySelector('#dashboard-headline');
const sectionTabs = document.querySelector('#section-tabs');
const dashboardRoot = document.querySelector('#dashboard-root');
const chartModal = document.querySelector('#chart-modal');
const chartModalTitle = document.querySelector('#chart-modal-title');
const chartModalSubtitle = document.querySelector('#chart-modal-subtitle');
const chartModalContent = document.querySelector('#chart-modal-content');

const colors = {
  previousBarStroke: '#9cbef6',
  targetBar: '#d7d7d7',
  actualBar: '#d40000',
  previousLine: '#bfd0ff',
  targetLine: '#8f8f8f',
  actualLine: '#d40000',
};

const state = {
  payload: null,
  activeSectionId: 'overall',
};

void init();

async function init() {
  try {
    const response = await fetch('./data/dashboard.json', { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`加载 dashboard.json 失败，HTTP ${response.status}`);
    }

    const payload = await response.json();
    const sections = Array.isArray(payload.dashboards) ? payload.dashboards : [];
    if (!sections.length) {
      throw new Error('dashboard.json 中没有可展示的来店趋势数据。');
    }

    state.payload = payload;
    state.activeSectionId = sections.some((item) => item.id === state.activeSectionId) ? state.activeSectionId : sections[0].id;

    renderMeta(payload.meta ?? {});
    dashboardHeadline.textContent = `趋势页会跟随 ${payload.meta?.reportScopeLabel ?? ''} 的工作簿缓存结果自动更新。`;
    renderTabs(sections);
    renderSection(sections.find((item) => item.id === state.activeSectionId) ?? sections[0]);
    bindModal();
  } catch (error) {
    renderError(error);
  }
}

function renderMeta(meta) {
  reportDateHighlight.innerHTML = `
    <span>报表日期</span>
    <strong>${escapeHtml(meta.reportDateLabel ?? '-')}</strong>
  `;

  metaStrip.innerHTML = '';
  [
    `统计周期：${meta.reportScopeLabel ?? '-'}`,
    `源文件：${meta.workbookName ?? '-'}`,
    `JSON 生成：${formatDateTime(meta.generatedAt)}`,
  ].forEach((text) => {
    const chip = document.createElement('span');
    chip.className = 'meta-chip';
    chip.textContent = text;
    metaStrip.appendChild(chip);
  });
}

function renderTabs(sections) {
  sectionTabs.innerHTML = '';
  sections.forEach((section) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = section.id === state.activeSectionId ? 'active' : '';
    button.textContent = section.title;
    button.addEventListener('click', () => {
      state.activeSectionId = section.id;
      renderTabs(sections);
      renderSection(section);
    });
    sectionTabs.appendChild(button);
  });
}

function renderSection(section) {
  dashboardRoot.innerHTML = '';

  const article = document.createElement('article');
  article.className = 'dashboard-card';
  article.innerHTML = `
    <header class="dashboard-header">
      <div>
        <p class="section-kicker">${escapeHtml((section.id ?? '').toUpperCase())}</p>
        <h2>${escapeHtml(section.title ?? '')}</h2>
      </div>
      <div class="dashboard-header-copy">
        <p>${escapeHtml(section.headline ?? '')}</p>
        <div class="source-pills">${(section.sourceRanges ?? [])
          .map((source) => `<span class="source-pill">${escapeHtml(source)}</span>`)
          .join('')}</div>
      </div>
    </header>
  `;

  const summaryGrid = document.createElement('div');
  summaryGrid.className = 'summary-grid';
  (section.summary?.cards ?? []).forEach((card) => {
    const node = document.createElement('article');
    node.className = 'summary-card';
    node.innerHTML = `
      <label>${escapeHtml(card.label ?? '')}</label>
      <strong>${escapeHtml(card.displayValue ?? '-')}</strong>
    `;
    summaryGrid.appendChild(node);
  });
  article.appendChild(summaryGrid);

  if (section.note) {
    const note = document.createElement('p');
    note.className = 'section-note';
    note.textContent = section.note;
    article.appendChild(note);
  }

  const layout = document.createElement('div');
  layout.className = 'dashboard-layout';

  const chartCard = document.createElement('section');
  chartCard.className = 'panel-card';
  chartCard.innerHTML = `
    <div class="card-topline">
      <div>
        <p class="section-kicker">Trend</p>
        <h3>${escapeHtml(section.trend?.chartTitle ?? '来店趋势')}</h3>
      </div>
      <span class="zoom-tip">点击图表可放大</span>
    </div>
  `;
  const chart = renderTrendChart(section.trend);
  chart.classList.add('clickable-chart');
  chart.addEventListener('click', () => openChartModal(section));
  chartCard.appendChild(chart);

  const tableCard = document.createElement('section');
  tableCard.className = 'panel-card';
  tableCard.innerHTML = `
    <div class="card-topline">
      <div>
        <p class="section-kicker">Table</p>
        <h3>明细对照表</h3>
      </div>
      <span class="source-pill">结构保持与 Excel 对照一致</span>
    </div>
  `;
  tableCard.appendChild(renderTrendBoard(section.trend));

  layout.appendChild(chartCard);
  layout.appendChild(tableCard);
  article.appendChild(layout);
  dashboardRoot.appendChild(article);
}

function renderTrendBoard(trend) {
  const rows = trend?.matrix?.rows ?? [];
  if (!rows.length) {
    return renderEmpty('当前没有可展示的明细表。');
  }

  const wrap = document.createElement('div');
  wrap.className = 'trend-matrix-wrap';
  const table = document.createElement('table');
  table.className = 'trend-matrix';

  table.innerHTML = `
    <thead>
      <tr>
        <th>维度</th>
        ${(trend.matrix.labels ?? []).map((label) => `<th>${escapeHtml(label)}</th>`).join('')}
      </tr>
    </thead>
    <tbody>
      ${rows
        .map((row) => {
          const cells = (row.displayValues ?? []).map((value, index) => {
            const className = index === (trend.reportDayIndex ?? -1) ? 'report-day' : '';
            return `<td class="${className}">${escapeHtml(value ?? '-')}</td>`;
          });
          return `<tr><th>${escapeHtml(row.label ?? '')}</th>${cells.join('')}</tr>`;
        })
        .join('')}
    </tbody>
  `;

  wrap.appendChild(table);
  return wrap;
}

function renderTrendChart(trend, options = {}) {
  const chart = trend;
  if (!chart?.labels?.length) {
    return renderEmpty('当前没有可绘制的趋势图。');
  }

  const wrapper = document.createElement('div');
  wrapper.className = `mixed-chart ${options.enlarged ? 'is-enlarged' : ''}`.trim();

  if (!options.enlarged) {
    const tip = document.createElement('span');
    tip.className = 'chart-zoom-hint';
    tip.textContent = '点击放大查看';
    wrapper.appendChild(tip);
  }

  const tooltip = document.createElement('div');
  tooltip.className = 'chart-tooltip';
  wrapper.appendChild(tooltip);

  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  const width = options.enlarged ? 1920 : 1480;
  const height = options.enlarged ? 760 : 620;
  const padding = options.enlarged
    ? { top: 42, right: 120, bottom: 108, left: 88 }
    : { top: 36, right: 96, bottom: 92, left: 74 };
  const minX = padding.left;
  const maxX = width - padding.right;
  const minY = padding.top;
  const maxY = height - padding.bottom;
  const plotHeight = maxY - minY;
  const bandWidth = (maxX - minX) / Math.max(chart.labels.length, 1);
  const dailyAxisMax = Math.max(chart.dailyAxisMax ?? 1, 1);
  const cumulativeAxisMax = Math.max(chart.cumulativeAxisMax ?? 1, 1);

  svg.setAttribute('viewBox', `0 0 ${width} ${height}`);

  for (let step = 0; step <= 3; step += 1) {
    const y = maxY - (plotHeight * step) / 3;
    svg.appendChild(createLine(minX, y, maxX, y, { stroke: 'rgba(29, 45, 56, 0.12)', 'stroke-width': '1.5' }));
    svg.appendChild(
      createText(minX - 12, y + 5, formatTick((dailyAxisMax / 3) * step), {
        'text-anchor': 'end',
        fill: 'rgba(29, 45, 56, 0.68)',
        'font-size': options.enlarged ? '18' : '14',
      }),
    );
    svg.appendChild(
      createText(maxX + 18, y + 5, formatTick((cumulativeAxisMax / 3) * step), {
        'text-anchor': 'start',
        fill: 'rgba(29, 45, 56, 0.68)',
        'font-size': options.enlarged ? '18' : '14',
      }),
    );
  }

  chart.labels.forEach((label, index) => {
    const centerX = getBandCenter(index, bandWidth, minX);
    const targetWidth = bandWidth * 0.44;
    const sideWidth = bandWidth * 0.18;

    drawBar(svg, centerX, chart.series?.target?.[index], dailyAxisMax, minY, maxY, targetWidth, {
      fill: colors.targetBar,
      opacity: '0.92',
    });
    drawBar(svg, centerX - bandWidth * 0.18, chart.series?.previousActual?.[index], dailyAxisMax, minY, maxY, sideWidth, {
      fill: 'rgba(255,255,255,0.95)',
      stroke: colors.previousBarStroke,
      'stroke-width': '1.4',
    });
    drawBar(svg, centerX + bandWidth * 0.18, chart.series?.actual?.[index], dailyAxisMax, minY, maxY, sideWidth, {
      fill: colors.actualBar,
    });

    const actualValue = chart.series?.actual?.[index];
    if (typeof actualValue === 'number' && Number.isFinite(actualValue)) {
      svg.appendChild(
        createText(centerX + bandWidth * 0.18, Math.max(scaleDaily(actualValue, dailyAxisMax, minY, maxY) - 8, minY + 12), formatCompact(actualValue), {
          'text-anchor': 'middle',
          fill: actualValue > 0 ? 'rgba(29, 45, 56, 0.76)' : 'rgba(29, 45, 56, 0.42)',
          'font-size': options.enlarged ? '16' : '12',
        }),
      );
    }

    svg.appendChild(
      createText(centerX, height - 28, label, {
        'text-anchor': 'middle',
        fill: index === (chart.reportDayIndex ?? -1) ? '#d40000' : 'rgba(29, 45, 56, 0.72)',
        'font-size': options.enlarged ? '16' : '13',
        'font-weight': index === (chart.reportDayIndex ?? -1) ? '700' : '500',
      }),
    );
  });

  getSeriesDefinitions().filter((item) => item.type === 'line').forEach((item) => {
    const points = buildLinePoints(chart.series?.[item.key] ?? [], cumulativeAxisMax, minX, bandWidth, minY, maxY);
    if (!points.some(Boolean)) {
      return;
    }
    const path = document.createElementNS(svg.namespaceURI, 'path');
    path.setAttribute('d', buildLinePath(points));
    path.setAttribute('fill', 'none');
    path.setAttribute('stroke', item.color);
    path.setAttribute('stroke-width', item.strokeWidth);
    path.setAttribute('stroke-linecap', 'round');
    path.setAttribute('stroke-linejoin', 'round');
    if (item.dashed) {
      path.setAttribute('stroke-dasharray', '8 6');
    }
    svg.appendChild(path);

    if (item.markers) {
      points.forEach((point) => {
        if (!point) {
          return;
        }
        const circle = document.createElementNS(svg.namespaceURI, 'circle');
        circle.setAttribute('cx', point.x);
        circle.setAttribute('cy', point.y);
        circle.setAttribute('r', item.markerRadius ?? 4.5);
        circle.setAttribute('fill', item.markerFill ?? item.color);
        circle.setAttribute('stroke', item.markerStroke ?? '#ffffff');
        circle.setAttribute('stroke-width', options.enlarged ? '2.4' : '2');
        svg.appendChild(circle);
      });
    }
  });

  chart.labels.forEach((_, index) => {
    const band = document.createElementNS(svg.namespaceURI, 'rect');
    band.setAttribute('x', String(minX + index * bandWidth));
    band.setAttribute('y', String(minY));
    band.setAttribute('width', String(bandWidth));
    band.setAttribute('height', String(plotHeight));
    band.setAttribute('fill', 'transparent');
    band.addEventListener('mouseenter', (event) => showTooltip(event, tooltip, chart, index));
    band.addEventListener('mousemove', (event) => moveTooltip(event, tooltip));
    band.addEventListener('mouseleave', () => hideTooltip(tooltip));
    svg.appendChild(band);
  });

  wrapper.appendChild(svg);

  const legend = document.createElement('div');
  legend.className = 'legend legend-wide';
  getSeriesDefinitions().forEach((item) => {
    const legendItem = document.createElement('span');
    legendItem.className = `legend-item ${hasNumericValues(chart.series?.[item.key]) ? '' : 'muted'}`.trim();
    const swatchStyle = getLegendSwatchStyle(item);
    legendItem.innerHTML = `<span class="legend-swatch ${item.type === 'line' ? 'line' : 'bar'}" style="${swatchStyle}"></span>${escapeHtml(item.label)}`;
    legend.appendChild(legendItem);
  });
  wrapper.appendChild(legend);

  return wrapper;
}

function getSeriesDefinitions() {
  return [
    {
      key: 'previousActual',
      label: '同期来店',
      type: 'bar',
      color: colors.previousBarStroke,
      fill: 'rgba(255,255,255,0.95)',
      stroke: colors.previousBarStroke,
      strokeWidth: 1.4,
    },
    { key: 'target', label: '本期目标', type: 'bar', color: colors.targetBar },
    { key: 'actual', label: '本期来店', type: 'bar', color: colors.actualBar },
    { key: 'cumulativeTarget', label: '本期累计目标', type: 'line', color: colors.targetLine, strokeWidth: '3', dashed: true },
    {
      key: 'cumulativeActual',
      label: '本期累计来店',
      type: 'line',
      color: colors.actualLine,
      strokeWidth: '3.6',
      markers: true,
      markerFill: '#ffffff',
      markerStroke: colors.actualLine,
      markerRadius: 4.6,
    },
    { key: 'previousCumulative', label: '上期累计来店', type: 'line', color: colors.previousLine, strokeWidth: '3' },
  ];
}

function bindModal() {
  chartModal.addEventListener('click', (event) => {
    if (event.target instanceof HTMLElement && event.target.dataset.closeModal === 'true') {
      closeChartModal();
    }
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && chartModal.classList.contains('visible')) {
      closeChartModal();
    }
  });
}

function openChartModal(section) {
  chartModalTitle.textContent = section.title ?? '';
  chartModalSubtitle.textContent = section.trend?.chartTitle ?? section.headline ?? '';
  chartModalContent.innerHTML = '';
  chartModalContent.appendChild(renderTrendChart(section.trend, { enlarged: true }));
  chartModal.classList.add('visible');
  document.body.classList.add('modal-open');
}

function closeChartModal() {
  chartModal.classList.remove('visible');
  document.body.classList.remove('modal-open');
}

function showTooltip(event, tooltip, chart, index) {
  const rows = getSeriesDefinitions()
    .map((item) => {
      const value = chart.series?.[item.key]?.[index];
      const dotStyle = getTooltipDotStyle(item);
      return `
        <div class="chart-tooltip-row">
          <span class="tooltip-series"><span class="tooltip-dot" style="${dotStyle}"></span>${escapeHtml(item.label)}</span>
          <strong>${escapeHtml(formatTooltipValue(value))}</strong>
        </div>
      `;
    })
    .join('');

  tooltip.innerHTML = `
    <div class="tooltip-date">${escapeHtml(chart.labels?.[index] ?? '-')}</div>
    ${rows}
  `;
  tooltip.classList.add('visible');
  moveTooltip(event, tooltip);
}

function moveTooltip(event, tooltip) {
  const frame = tooltip.parentElement.getBoundingClientRect();
  tooltip.style.left = `${event.clientX - frame.left + 14}px`;
  tooltip.style.top = `${event.clientY - frame.top - 14}px`;
}

function hideTooltip(tooltip) {
  tooltip.classList.remove('visible');
}

function getTooltipDotStyle(item) {
  if (item.key === 'previousActual') {
    return `background: rgba(255,255,255,0.96); border: 2px solid ${item.stroke ?? item.color};`;
  }

  return `background: ${item.color}; border: 2px solid ${item.color};`;
}

function getLegendSwatchStyle(item) {
  if (item.type === 'line') {
    return `--swatch:${item.color}; --swatch-accent:${item.accent ?? item.color};`;
  }

  return [
    `--swatch:${item.color}`,
    `--swatch-accent:${item.accent ?? item.color}`,
    `--swatch-fill:${item.fill ?? item.color}`,
    `--swatch-border:${item.stroke ?? item.accent ?? item.color}`,
    `--swatch-border-width:${item.strokeWidth ?? 1.5}px`,
  ].join('; ');
}

function drawBar(svg, centerX, value, axisMax, minY, maxY, width, attrs) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return;
  }
  const y = scaleDaily(value, axisMax, minY, maxY);
  const rect = document.createElementNS(svg.namespaceURI, 'rect');
  rect.setAttribute('x', String(centerX - width / 2));
  rect.setAttribute('y', String(y));
  rect.setAttribute('width', String(width));
  rect.setAttribute('height', String(Math.max(maxY - y, 0.8)));
  Object.entries(attrs).forEach(([key, attrValue]) => rect.setAttribute(key, attrValue));
  svg.appendChild(rect);
}

function buildLinePoints(values, axisMax, minX, bandWidth, minY, maxY) {
  return values.map((value, index) => {
    if (typeof value !== 'number' || !Number.isFinite(value)) {
      return null;
    }
    return {
      x: getBandCenter(index, bandWidth, minX),
      y: scaleCumulative(value, axisMax, minY, maxY),
    };
  });
}

function buildLinePath(points) {
  let path = '';
  let started = false;
  points.forEach((point) => {
    if (!point) {
      started = false;
      return;
    }
    path += `${started ? ' L' : 'M'} ${point.x} ${point.y}`;
    started = true;
  });
  return path.trim();
}

function createLine(x1, y1, x2, y2, attrs) {
  const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
  line.setAttribute('x1', x1);
  line.setAttribute('y1', y1);
  line.setAttribute('x2', x2);
  line.setAttribute('y2', y2);
  Object.entries(attrs).forEach(([key, value]) => line.setAttribute(key, value));
  return line;
}

function createText(x, y, text, attrs) {
  const node = document.createElementNS('http://www.w3.org/2000/svg', 'text');
  node.setAttribute('x', x);
  node.setAttribute('y', y);
  Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value));
  node.textContent = text;
  return node;
}

function scaleDaily(value, axisMax, minY, maxY) {
  return maxY - (value / axisMax) * (maxY - minY);
}

function scaleCumulative(value, axisMax, minY, maxY) {
  return maxY - (value / axisMax) * (maxY - minY);
}

function getBandCenter(index, bandWidth, minX) {
  return minX + index * bandWidth + bandWidth / 2;
}

function hasNumericValues(values) {
  return Array.isArray(values) && values.some((value) => typeof value === 'number' && Number.isFinite(value));
}

function formatTick(value) {
  if (!value) {
    return '0';
  }
  if (value >= 10000) {
    return `${Math.round(value / 1000)}k`;
  }
  return String(Math.round(value));
}

function formatCompact(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '-';
  }
  return Math.round(value).toString();
}

function formatTooltipValue(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return '-';
  }
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 0 }).format(value);
}

function renderError(error) {
  const message = error instanceof Error ? error.message : String(error);
  dashboardRoot.innerHTML = `<article class="panel-card"><strong>${escapeHtml(message)}</strong></article>`;
}

function renderEmpty(message) {
  const block = document.createElement('div');
  block.className = 'empty-state';
  block.innerHTML = `<strong>${escapeHtml(message)}</strong>`;
  return block;
}

function formatDateTime(value) {
  return value ? String(value).replace('T', ' ') : '-';
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}
