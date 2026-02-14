import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import LanguageDetector from 'i18next-browser-languagedetector';

import zh from './locales/zh.json';
import en from './locales/en.json';

// Map config language codes to i18next
const LANGUAGE_MAP = {
  'zh-CN': 'zh',
  'zh': 'zh',
  'en-US': 'en',
  'en': 'en',
};

export function configLangToI18n(configLang) {
  return LANGUAGE_MAP[configLang] || 'en';
}

export function i18nLangToConfig(i18nLang) {
  if (i18nLang === 'zh' || i18nLang?.startsWith('zh')) return 'zh-CN';
  return 'en-US';
}

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: {
      zh: { translation: zh },
      'zh-CN': { translation: zh },
      en: { translation: en },
      'en-US': { translation: en },
    },
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false,
    },
    detection: {
      order: ['localStorage', 'navigator'],
      caches: ['localStorage'],
      lookupLocalStorage: 'i18nextLng',
    },
  });

export default i18n;
