import { useEffect } from 'react';
import { getAppConfig } from '../utils/configApi';
import i18n, { configLangToI18n } from '../i18n';

/**
 * Syncs config.language to i18n on app load.
 * Renders children; runs side effect to apply language from config.
 */
export default function I18nConfigSync({ children }) {
  useEffect(() => {
    getAppConfig().then((config) => {
      const lang = config?.language || 'zh-CN';
      const i18nLang = configLangToI18n(lang);
      if (i18n.language !== i18nLang) {
        i18n.changeLanguage(i18nLang);
      }
    }).catch(() => {});
  }, []);

  return children;
}
