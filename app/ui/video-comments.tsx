"use client";

import React, { useState, useEffect, useCallback } from "react";
import { 
  fetchPublicVideoComments, 
  postPublicVideoComment, 
  votePublicVideoComment, 
  VideoComment 
} from "@/app/public-data";

function formatDate(dateStr: string | undefined | null) {
  if (!dateStr) return "";
  try {
    const d = new Date(dateStr);
    return new Intl.DateTimeFormat("en-US", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }).format(d);
  } catch {
    return dateStr;
  }
}

export default function VideoComments({ videoId }: { videoId: string }) {
  const [comments, setComments] = useState<VideoComment[]>([]);
  const [newComment, setNewComment] = useState("");
  const [submittingComment, setSubmittingComment] = useState(false);
  const [replyingTo, setReplyingTo] = useState<number | null>(null);
  const [replyText, setReplyText] = useState("");
  const [isExpanded, setIsExpanded] = useState(false);
  
  // Track votes in memory and localStorage for optimistic UI and preventing multiple votes
  const [votedComments, setVotedComments] = useState<Record<number, "like" | "dislike">>({});

  useEffect(() => {
    try {
      const stored = localStorage.getItem(`voted_comments`);
      if (stored) {
        setVotedComments(JSON.parse(stored));
      }
    } catch {}
  }, []);

  const loadComments = useCallback(async () => {
    if (!videoId) return;
    const data = await fetchPublicVideoComments(videoId);
    setComments(data);
  }, [videoId]);

  useEffect(() => {
    loadComments().catch(console.error);
  }, [loadComments]);

  const handlePostComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newComment.trim()) return;
    setSubmittingComment(true);
    const success = await postPublicVideoComment(videoId, newComment.trim());
    if (success) {
      setNewComment("");
      await loadComments();
    }
    setSubmittingComment(false);
  };

  const handlePostReply = async (e: React.FormEvent, parentId: number) => {
    e.preventDefault();
    if (!replyText.trim()) return;
    setSubmittingComment(true);
    const success = await postPublicVideoComment(videoId, replyText.trim(), parentId);
    if (success) {
      setReplyingTo(null);
      setReplyText("");
      await loadComments();
    }
    setSubmittingComment(false);
  };

  const handleVote = async (commentId: number, action: "like" | "dislike") => {
    if (votedComments[commentId] === action) return; // already voted this way

    // Optimistic update
    setComments(prev => prev.map(c => {
      if (c.id === commentId) {
        const cLike = c.like_count || 0;
        const cDislike = c.dislike_count || 0;
        let newLike = cLike;
        let newDislike = cDislike;

        if (action === "like") {
          newLike++;
          if (votedComments[commentId] === "dislike") newDislike--; // switch vote
        } else {
          newDislike++;
          if (votedComments[commentId] === "like") newLike--; // switch vote
        }

        return { ...c, like_count: Math.max(0, newLike), dislike_count: Math.max(0, newDislike) };
      }
      return c;
    }));
    
    const newVoted = { ...votedComments, [commentId]: action };
    setVotedComments(newVoted);
    try { localStorage.setItem(`voted_comments`, JSON.stringify(newVoted)); } catch {}

    const res = await votePublicVideoComment(commentId, action);
    if (res.success) {
      setComments(prev => prev.map(c => 
        c.id === commentId ? { ...c, like_count: res.like_count, dislike_count: res.dislike_count } : c
      ));
    }
  };

  // Group comments into a tree
  const rootComments = comments.filter(c => !c.parent_id);
  const repliesByParent: Record<number, VideoComment[]> = {};
  comments.filter(c => c.parent_id).forEach(c => {
    if (!repliesByParent[c.parent_id!]) repliesByParent[c.parent_id!] = [];
    repliesByParent[c.parent_id!].push(c);
  });
  
  // Sort replies oldest first
  Object.values(repliesByParent).forEach(list => list.sort((a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()));

  const renderCommentTree = (c: VideoComment, isReply = false) => {
    const hasReplies = repliesByParent[c.id] && repliesByParent[c.id].length > 0;
    
    return (
      <div key={c.id} className={`flex gap-4 ${isReply ? 'mt-4' : ''}`}>
        <div className="w-10 h-10 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center text-blue-600 font-bold shrink-0">
          {(c.author_name || "A")[0].toUpperCase()}
        </div>
        <div className="flex-1">
          <div className="flex items-baseline gap-2 mb-1">
            <span className="font-bold text-sm text-gray-900 dark:text-white">{c.author_name}</span>
            <span className="text-xs text-gray-500">{formatDate(c.created_at)}</span>
          </div>
          <p className="text-sm text-gray-800 dark:text-gray-200 whitespace-pre-wrap">{c.comment_text}</p>
          
          <div className="flex items-center gap-4 mt-2 text-gray-500 dark:text-gray-400">
            <button 
              onClick={() => handleVote(c.id, "like")} 
              className={`flex items-center gap-1 text-xs hover:text-blue-600 transition-colors ${votedComments[c.id] === 'like' ? 'text-blue-600' : ''}`}
            >
              <svg className="w-4 h-4" fill={votedComments[c.id] === 'like' ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg>
              <span>{c.like_count || ""}</span>
            </button>
            <button 
              onClick={() => handleVote(c.id, "dislike")} 
              className={`flex items-center gap-1 text-xs hover:text-blue-600 transition-colors ${votedComments[c.id] === 'dislike' ? 'text-blue-600' : ''}`}
            >
              <svg className="w-4 h-4" fill={votedComments[c.id] === 'dislike' ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2a2 2 0 0 1 2 2v7a2 2 0 0 1-2 2h-2"></path></svg>
              <span>{c.dislike_count || ""}</span>
            </button>
            {!isReply && (
              <button 
                onClick={() => { setReplyingTo(replyingTo === c.id ? null : c.id); setReplyText(""); }} 
                className="text-xs font-semibold hover:text-blue-600 transition-colors"
              >
                Javob berish
              </button>
            )}
          </div>

          {replyingTo === c.id && (
            <form onSubmit={(e) => handlePostReply(e, c.id)} className="mt-4 flex gap-3">
              <div className="w-8 h-8 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center text-gray-500 font-bold shrink-0">
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
              </div>
              <div className="flex-1 flex flex-col gap-2">
                <input
                  type="text"
                  placeholder="Javob yozish..."
                  value={replyText}
                  onChange={e => setReplyText(e.target.value)}
                  className="w-full bg-transparent border-b border-gray-300 dark:border-gray-600 focus:border-gray-900 dark:focus:border-white outline-none py-1 px-1 text-sm text-gray-900 dark:text-white transition-colors"
                  autoFocus
                  required
                />
                <div className="flex justify-end gap-2 mt-1">
                  <button
                    type="button"
                    onClick={() => { setReplyingTo(null); setReplyText(""); }}
                    className="px-3 py-1.5 text-xs font-semibold rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300"
                  >
                    Bekor qilish
                  </button>
                  <button
                    type="submit"
                    disabled={submittingComment || !replyText.trim()}
                    className="px-3 py-1.5 text-xs font-semibold rounded-full bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
                  >
                    {submittingComment ? "..." : "Javob yozish"}
                  </button>
                </div>
              </div>
            </form>
          )}

          {hasReplies && (
            <div className="mt-4">
              {repliesByParent[c.id].map(reply => renderCommentTree(reply, true))}
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <>
      {/* Mobile Comment Preview Box */}
      {!isExpanded && (
        <div 
          onClick={() => setIsExpanded(true)} 
          className="lg:hidden bg-gray-100 dark:bg-gray-800/80 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors rounded-2xl p-3 my-4 cursor-pointer"
        >
          <div className="flex justify-between items-center mb-1.5">
            <span className="font-bold text-sm text-gray-900 dark:text-white">Fikrlar • {comments.length}</span>
            <svg className="w-4 h-4 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
          </div>
          {comments.length > 0 ? (
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/50 text-blue-600 dark:text-blue-400 text-[10px] flex shrink-0 items-center justify-center font-bold">
                {(comments[0].author_name || "A")[0].toUpperCase()}
              </div>
              <span className="text-xs text-gray-700 dark:text-gray-300 line-clamp-1">{comments[0].comment_text}</span>
            </div>
          ) : (
            <span className="text-xs text-gray-500 dark:text-gray-400">Izoh qoldirgan birinchi inson bo'ling...</span>
          )}
        </div>
      )}

      {/* Full Comments Section */}
      <div className={`${isExpanded ? "block" : "hidden lg:block"} video-comments-section mt-6 pt-6 border-t border-gray-200 dark:border-gray-800`}>
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white">
            {comments.length} Fikrlar
          </h2>
          {isExpanded && (
            <button 
              onClick={() => setIsExpanded(false)} 
              className="lg:hidden p-2 bg-gray-100 dark:bg-gray-800 rounded-full text-gray-500 hover:text-gray-900 dark:hover:text-white"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
            </button>
          )}
        </div>

        <form onSubmit={handlePostComment} className="mb-8 flex gap-4">
          <div className="w-10 h-10 rounded-full bg-gray-200 dark:bg-gray-700 flex items-center justify-center text-gray-500 font-bold shrink-0">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" /></svg>
          </div>
          <div className="flex-1 flex flex-col gap-2">
            <input
              type="text"
              placeholder="Fikr bildirish..."
              value={newComment}
              onChange={e => setNewComment(e.target.value)}
              className="w-full bg-transparent border-b border-gray-300 dark:border-gray-600 focus:border-gray-900 dark:focus:border-white outline-none py-1 px-1 text-sm text-gray-900 dark:text-white transition-colors"
              required
            />
            {newComment.trim().length > 0 && (
              <div className="flex justify-end gap-2 mt-2">
                <button
                  type="button"
                  onClick={() => setNewComment("")}
                  className="px-4 py-2 text-sm font-semibold rounded-full hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300"
                >
                  Bekor qilish
                </button>
                <button
                  type="submit"
                  disabled={submittingComment}
                  className="px-4 py-2 text-sm font-semibold rounded-full bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50"
                >
                  {submittingComment ? "Yuborilmoqda..." : "Yuborish"}
                </button>
              </div>
            )}
          </div>
        </form>

        <div className="flex flex-col gap-6">
          {rootComments.map(c => renderCommentTree(c))}
        </div>
      </div>
    </>
  );
}
