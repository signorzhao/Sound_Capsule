import i18n from '../i18n';

/**
 * 根据当前语言获取标签的展示文本
 * @param {Object} tag - 标签对象，包含 word_cn, word_en, word, zh, en 等字段
 * @param {string} [lang] - 可选，指定语言；不传则使用 i18n 当前语言
 * @returns {string} 展示文本
 */
export function getTagDisplayText(tag, lang) {
  if (!tag) return '';
  const l = lang || i18n.language || 'zh';
  const isEn = l === 'en' || l?.startsWith('en');
  if (isEn) {
    return tag.word_en || tag.en || tag.word || tag.word_cn || tag.zh || '';
  }
  return tag.word_cn || tag.zh || tag.word_en || tag.en || tag.word || '';
}
