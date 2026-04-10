const reportDateHighlight = document.querySelector('#report-date-highlight');
const metaStrip = document.querySelector('#meta-strip');
const homeHeadline = document.querySelector('#home-headline');
const scopeLabel = document.querySelector('#scope-label');
const briefSource = document.querySelector('#brief-source');
const briefTemplateContent = document.querySelector('#brief-template-content');
const metricCluster = document.querySelector('#metric-cluster');
const narrativeList = document.querySelector('#narrative-list');
const arrivalLink = document.querySelector('#arrival-link');

void init();

async function init() {
  try {
    const response = await fetch('./data/dashboard.json', { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`加载 dashboard.json 失败，HTTP ${response.status}`);
    }

    const payload = await response.json();
    renderMeta(payload.meta ?? {});
    renderHome(payload.home ?? {});
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
    `更新时间：${formatDateTime(meta.workbookModifiedAt)}`,
  ].forEach((text) => {
    const chip = document.createElement('span');
    chip.className = 'meta-chip';
    chip.textContent = text;
    metaStrip.appendChild(chip);
  });
}

function renderHome(home) {
  homeHeadline.textContent = home.headline ?? '';
  scopeLabel.textContent = `当前简报直接读取 Excel 当天缓存值，更新工作簿并重新生成 JSON 后，首页和趋势页会一起刷新。`;
  briefSource.textContent = home.briefBlock?.sourceCell ?? '';

  if (home.jump?.href) {
    arrivalLink.href = home.jump.href;
  }
  if (home.jump?.label) {
    arrivalLink.textContent = home.jump.label;
  }

  const lines = home.briefBlock?.lines ?? [];
  briefTemplateContent.innerHTML = '';
  lines.forEach((line, index) => {
    const paragraph = document.createElement('p');
    paragraph.className = index === 0 ? 'brief-template-title' : 'brief-template-line';
    paragraph.textContent = line;
    briefTemplateContent.appendChild(paragraph);
  });

  metricCluster.innerHTML = '';
  (home.cards ?? []).forEach((card) => {
    const article = document.createElement('article');
    article.className = `metric-card metric-card-${card.tone ?? 'default'}`;
    article.innerHTML = `
      <label>${escapeHtml(card.label ?? '')}</label>
      <strong>${escapeHtml(card.displayValue ?? '-')}</strong>
    `;
    metricCluster.appendChild(article);
  });

  narrativeList.innerHTML = '';
  (home.narratives ?? []).forEach((line) => {
    const article = document.createElement('article');
    article.className = 'narrative-item';
    article.innerHTML = `<p>${escapeHtml(line)}</p>`;
    narrativeList.appendChild(article);
  });
}

function renderError(error) {
  const message = error instanceof Error ? error.message : String(error);
  homeHeadline.textContent = '数据加载失败';
  briefTemplateContent.innerHTML = `<p class="brief-template-line">${escapeHtml(message)}</p>`;
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
