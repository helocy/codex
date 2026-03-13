import { useState, useEffect } from 'react';
import { Language, translations } from './locales';

const STORAGE_KEY = 'codex_language';

export function useTranslation() {
  const [language, setLanguage] = useState<Language>(() => {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'zh' || saved === 'en') {
      return saved;
    }
    // 自动检测浏览器语言
    const browserLang = navigator.language.toLowerCase();
    if (browserLang.startsWith('zh')) {
      return 'zh';
    }
    return 'en';
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, language);
  }, [language]);

  const t = translations[language];

  const switchLanguage = (lang: Language) => {
    setLanguage(lang);
  };

  return { t, language, switchLanguage };
}
