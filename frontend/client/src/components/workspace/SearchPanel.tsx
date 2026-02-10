import { useState, useCallback } from "react";
import { useMutation } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Search,
  MessageSquare,
  FileText,
  Loader2,
  Send,
  Sparkles,
} from "lucide-react";
import { api, SearchResult, QuestionResponse, QuestionSource } from "@/lib/api";

interface SearchPanelProps {
  onDocumentClick?: (documentId: string) => void;
}

export function SearchPanel({ onDocumentClick }: SearchPanelProps) {
  const [query, setQuery] = useState("");
  const [mode, setMode] = useState<"search" | "qa">("qa");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [qaResult, setQaResult] = useState<QuestionResponse | null>(null);

  const searchMutation = useMutation({
    mutationFn: (q: string) => api.semanticSearch(q, 10),
    onSuccess: (data) => {
      setSearchResults(data.results);
      setQaResult(null);
    },
  });

  const qaMutation = useMutation({
    mutationFn: (question: string) => api.askQuestion(question),
    onSuccess: (data) => {
      setQaResult(data);
      setSearchResults([]);
    },
  });

  const handleSubmit = useCallback(() => {
    if (!query.trim()) return;
    
    if (mode === "search") {
      searchMutation.mutate(query);
    } else {
      qaMutation.mutate(query);
    }
  }, [query, mode, searchMutation, qaMutation]);

  const isLoading = searchMutation.isPending || qaMutation.isPending;

  return (
    <div className="h-full flex flex-col gap-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Search & Q&A</h2>
          <p className="text-muted-foreground text-sm mt-1">
            Search your documents or ask questions about your data
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant={mode === "qa" ? "default" : "outline"}
            size="sm"
            onClick={() => setMode("qa")}
            className="gap-2"
          >
            <MessageSquare className="h-4 w-4" />
            Ask a Question
          </Button>
          <Button
            variant={mode === "search" ? "default" : "outline"}
            size="sm"
            onClick={() => setMode("search")}
            className="gap-2"
          >
            <Search className="h-4 w-4" />
            Semantic Search
          </Button>
        </div>
      </div>

      {/* Search Input */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={
                  mode === "qa"
                    ? "Ask a question about your documents..."
                    : "Search for relevant content..."
                }
                className="pr-10"
                onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
              />
              {mode === "qa" && (
                <Sparkles className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-purple-400" />
              )}
            </div>
            <Button onClick={handleSubmit} disabled={isLoading || !query.trim()}>
              {isLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Results */}
      <div className="flex-1 min-h-0">
        {isLoading ? (
          <Card className="h-full">
            <CardContent className="pt-6 space-y-4">
              <Skeleton className="h-4 w-3/4" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-5/6" />
              <Skeleton className="h-4 w-2/3" />
            </CardContent>
          </Card>
        ) : qaResult ? (
          <div className="space-y-4">
            {/* Q&A Answer */}
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Sparkles className="h-5 w-5 text-purple-400" />
                    Answer
                  </CardTitle>
                  <Badge 
                    variant="outline" 
                    className={
                      qaResult.confidence > 0.7 
                        ? "border-emerald-500 text-emerald-500" 
                        : qaResult.confidence > 0.4 
                        ? "border-amber-500 text-amber-500"
                        : "border-red-500 text-red-500"
                    }
                  >
                    {Math.round(qaResult.confidence * 100)}% confidence
                  </Badge>
                </div>
              </CardHeader>
              <CardContent>
                <p className="text-muted-foreground leading-relaxed whitespace-pre-wrap">
                  {qaResult.answer}
                </p>
              </CardContent>
            </Card>

            {/* Sources */}
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-lg">Sources ({qaResult.sources.length})</CardTitle>
              </CardHeader>
              <CardContent>
                <ScrollArea className="h-[300px]">
                  <div className="space-y-3">
                    {qaResult.sources.map((source, idx) => (
                      <div
                        key={idx}
                        className={`p-3 rounded border cursor-pointer hover:border-primary/50 transition-colors ${
                          qaResult.referenced_sources.includes(idx + 1)
                            ? "border-primary/30 bg-primary/5"
                            : "border-border"
                        }`}
                        onClick={() => onDocumentClick?.(source.document_id)}
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <FileText className="h-4 w-4 text-muted-foreground" />
                            <span className="font-medium text-sm">{source.filename}</span>
                            {qaResult.referenced_sources.includes(idx + 1) && (
                              <Badge variant="secondary" className="text-[10px]">
                                Used
                              </Badge>
                            )}
                          </div>
                          <Badge variant="outline" className="text-[10px]">
                            {Math.round(source.similarity * 100)}% match
                          </Badge>
                        </div>
                        <p className="text-xs text-muted-foreground line-clamp-3">
                          {source.excerpt}
                        </p>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              </CardContent>
            </Card>
          </div>
        ) : searchResults.length > 0 ? (
          <Card className="h-full">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg">Search Results ({searchResults.length})</CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-[400px]">
                <div className="space-y-3">
                  {searchResults.map((result, idx) => (
                    <div
                      key={idx}
                      className="p-3 rounded border border-border cursor-pointer hover:border-primary/50 transition-colors"
                      onClick={() => onDocumentClick?.(result.document_id)}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <FileText className="h-4 w-4 text-muted-foreground" />
                          <span className="font-medium text-sm">{result.filename}</span>
                          <Badge variant="outline" className="text-[10px]">
                            Chunk {result.chunk_index + 1}
                          </Badge>
                        </div>
                        <Badge 
                          variant="outline" 
                          className={
                            result.similarity > 0.7 
                              ? "border-emerald-500 text-emerald-500" 
                              : result.similarity > 0.4 
                              ? "border-amber-500 text-amber-500"
                              : "border-muted-foreground"
                          }
                        >
                          {Math.round(result.similarity * 100)}% match
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-4">
                        {result.content}
                      </p>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        ) : (
          <Card className="h-full flex items-center justify-center">
            <CardContent className="text-center text-muted-foreground py-12">
              <Search className="h-12 w-12 mx-auto mb-4 opacity-50" />
              <p className="text-lg font-medium">
                {mode === "qa" ? "Ask a question about your documents" : "Search your document corpus"}
              </p>
              <p className="text-sm mt-1">
                {mode === "qa" 
                  ? "I'll find relevant context and generate an answer"
                  : "I'll find the most semantically similar content"
                }
              </p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
