import { Link } from 'react-router-dom';
import { useDocumentTitle } from '@/hooks/useDocumentTitle';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { FileQuestion, Home, ArrowLeft } from 'lucide-react';

export default function NotFoundPage() {
  useDocumentTitle('页面未找到');
  return (
    <div className="flex min-h-[70vh] items-center justify-center p-8">
      <Card className="w-full max-w-md text-center">
        <CardHeader>
          <FileQuestion className="mx-auto h-16 w-16 text-muted-foreground/40" />
          <CardTitle className="text-4xl font-bold text-muted-foreground/30">
            404
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-muted-foreground">
            你访问的页面不存在，可能已被移动或删除
          </p>
          <div className="flex justify-center gap-3">
            <Button variant="outline" asChild>
              <Link to="/" className="gap-2">
                <Home className="h-4 w-4" />
                返回首页
              </Link>
            </Button>
            <Button variant="ghost" onClick={() => window.history.back()}>
              <ArrowLeft className="mr-2 h-4 w-4" />
              后退
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}