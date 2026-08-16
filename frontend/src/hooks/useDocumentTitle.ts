import { useEffect } from 'react';

const BASE_TITLE = '织网鉴真 TruthNet';

export function useDocumentTitle(title?: string) {
  useEffect(() => {
    if (!title) {
      document.title = BASE_TITLE;
      return;
    }
    document.title = `${title} - ${BASE_TITLE}`;
  }, [title]);
}