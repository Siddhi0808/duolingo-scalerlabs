"use client";

import { use, useEffect, useState, useCallback, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { api, ApiClientError } from "@/lib/api/client";
import { queryKeys, useMe } from "@/lib/api/hooks";
import {
  playCompleteSound,
  playCorrectSound,
  playIncorrectSound,
} from "@/lib/audio";
import type {
  Answer,
  AnswerRequest,
  AnswerResult,
  HeartInfo,
  PublicExercise,
  SessionProgress,
} from "@/lib/api/types";

import { LessonHeader } from "@/components/lesson/LessonHeader";
import { FeedbackSheet } from "@/components/lesson/FeedbackSheet";
import { QuitModal } from "@/components/lesson/QuitModal";
import { OutOfHeartsModal } from "@/components/lesson/OutOfHeartsModal";
import { LessonCompleteScreen } from "@/components/lesson/LessonCompleteScreen";
import { MultipleChoiceExercise } from "@/components/lesson/MultipleChoiceExercise";
import { WordBankExercise } from "@/components/lesson/WordBankExercise";
import { MatchingPairsExercise } from "@/components/lesson/MatchingPairsExercise";
import { FillBlankExercise } from "@/components/lesson/FillBlankExercise";
import { TypeAnswerExercise } from "@/components/lesson/TypeAnswerExercise";
import { ErrorState } from "@/components/common/ErrorState";

interface LessonPageProps {
  params: Promise<{ id: string }>;
}

export default function LessonPage({ params }: LessonPageProps) {
  const resolvedParams = use(params);
  const lessonId = parseInt(resolvedParams.id, 10);
  const router = useRouter();
  const queryClient = useQueryClient();
  const [, startTransition] = useTransition();

  // Session state
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentExercise, setCurrentExercise] = useState<PublicExercise | null>(null);
  const [progress, setProgress] = useState<SessionProgress | undefined>(undefined);
  const [hearts, setHearts] = useState<HeartInfo | undefined>(undefined);
  const { data: me } = useMe();
  const gems = me?.gems;

  // Status flags
  const [isLoading, setIsLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isQuitting, setIsQuitting] = useState(false);
  const [isRefilling, setIsRefilling] = useState(false);
  const [refillError, setRefillError] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<{ code: string; message: string } | null>(null);

  // Modals & Sheets
  const [showQuitModal, setShowQuitModal] = useState(false);
  const [showOutOfHeartsModal, setShowOutOfHeartsModal] = useState(false);
  const [answerResult, setAnswerResult] = useState<AnswerResult | null>(null);
  const [completedRewards, setCompletedRewards] = useState<AnswerResult["rewards"] | null>(null);

  // Interactive answer state for current exercise
  const [mcOptionId, setMcOptionId] = useState<string | null>(null);
  const [wbTileIds, setWbTileIds] = useState<string[]>([]);
  const [mpPairs, setMpPairs] = useState<[string, string][]>([]);
  const [mpSelectedLeft, setMpSelectedLeft] = useState<string | null>(null);
  const [mpSelectedRight, setMpSelectedRight] = useState<string | null>(null);
  const [fbText, setFbText] = useState<string | null>(null);
  const [taText, setTaText] = useState<string>("");

  // Clear exercise inputs
  const resetExerciseInputs = useCallback(() => {
    setMcOptionId(null);
    setWbTileIds([]);
    setMpPairs([]);
    setMpSelectedLeft(null);
    setMpSelectedRight(null);
    setFbText(null);
    setTaText("");
  }, []);

  // Initialize or resume lesson session
  const [initTrigger, setInitTrigger] = useState(0);

  useEffect(() => {
    let ignore = false;

    async function load() {
      if (isNaN(lessonId)) {
        setErrorMessage({ code: "INVALID_ID", message: "Invalid lesson ID." });
        setIsLoading(false);
        return;
      }

      try {
        const res = await api.startLesson(lessonId);
        if (ignore) return;
        setSessionId(res.session_id);
        setProgress(res.progress);
        setHearts(res.hearts);
        setCurrentExercise(res.current_exercise);
        setAnswerResult(null);
        resetExerciseInputs();

        if (res.hearts.current <= 0) {
          setShowOutOfHeartsModal(true);
        }
      } catch (err) {
        if (ignore) return;
        if (err instanceof ApiClientError) {
          if (err.code === "NO_HEARTS") {
            setShowOutOfHeartsModal(true);
            const detailsHearts = err.details?.hearts as HeartInfo | undefined;
            if (detailsHearts) setHearts(detailsHearts);
          } else {
            setErrorMessage({ code: err.code, message: err.message });
          }
        } else {
          setErrorMessage({
            code: "NETWORK_ERROR",
            message: err instanceof Error ? err.message : "Failed to load lesson.",
          });
        }
      } finally {
        if (!ignore) setIsLoading(false);
      }
    }

    load();
    return () => {
      ignore = true;
    };
  }, [lessonId, initTrigger, resetExerciseInputs]);

  // Handle Matching Pairs selection logic
  const handleSelectLeft = (leftId: string) => {
    if (mpSelectedRight) {
      // Form pair
      setMpPairs((prev) => [...prev.filter((p) => p[0] !== leftId && p[1] !== mpSelectedRight), [leftId, mpSelectedRight]]);
      setMpSelectedLeft(null);
      setMpSelectedRight(null);
    } else {
      setMpSelectedLeft(leftId);
    }
  };

  const handleSelectRight = (rightId: string) => {
    if (mpSelectedLeft) {
      // Form pair
      setMpPairs((prev) => [...prev.filter((p) => p[0] !== mpSelectedLeft && p[1] !== rightId), [mpSelectedLeft, rightId]]);
      setMpSelectedLeft(null);
      setMpSelectedRight(null);
    } else {
      setMpSelectedRight(rightId);
    }
  };

  const handleUnpair = (leftId: string) => {
    setMpPairs((prev) => prev.filter((p) => p[0] !== leftId));
  };

  // Determine if current input satisfies structural UI requirements to submit
  const canCheck = Boolean(
    currentExercise &&
      !answerResult &&
      !isSubmitting &&
      (currentExercise.type === "multiple_choice"
        ? mcOptionId !== null
        : currentExercise.type === "word_bank"
        ? wbTileIds.length > 0
        : currentExercise.type === "matching_pairs"
        ? mpPairs.length === currentExercise.payload.left.length
        : currentExercise.type === "fill_blank"
        ? fbText !== null && fbText.trim().length > 0
        : currentExercise.type === "type_answer"
        ? taText.trim().length > 0
        : false)
  );

  // Submit Answer to backend
  const handleSubmitAnswer = async () => {
    if (!sessionId || !currentExercise || !canCheck || isSubmitting) return;

    let answer: Answer;
    switch (currentExercise.type) {
      case "multiple_choice":
        if (!mcOptionId) return;
        answer = { type: "multiple_choice", option_id: mcOptionId };
        break;
      case "word_bank":
        if (wbTileIds.length === 0) return;
        answer = { type: "word_bank", tile_ids: wbTileIds };
        break;
      case "matching_pairs":
        answer = { type: "matching_pairs", pairs: mpPairs };
        break;
      case "fill_blank":
        if (!fbText) return;
        answer = { type: "fill_blank", text: fbText };
        break;
      case "type_answer":
        if (!taText.trim()) return;
        answer = { type: "type_answer", text: taText.trim() };
        break;
      default:
        return;
    }

    const request: AnswerRequest = {
      exercise_id: currentExercise.id,
      answer,
    };

    setIsSubmitting(true);

    try {
      const res = await api.submitAnswer(sessionId, request);
      setAnswerResult(res);
      setHearts(res.hearts);
      setProgress(res.progress);

      if (res.correct) {
        playCorrectSound();
      } else {
        playIncorrectSound();
      }

      if (res.rewards) {
        playCompleteSound();
      }
    } catch (err) {
      if (err instanceof ApiClientError) {
        if (err.code === "NO_HEARTS") {
          setShowOutOfHeartsModal(true);
        } else if (err.code === "EXERCISE_NOT_CURRENT") {
          // Sync with server's current exercise
          try {
            const ex = await api.getCurrentExercise(sessionId);
            setCurrentExercise(ex);
            resetExerciseInputs();
          } catch {
            setErrorMessage({ code: err.code, message: "Please refresh to resume the current exercise." });
          }
        } else if (err.code === "SESSION_NOT_ACTIVE") {
          // Re-fetch session
          try {
            const session = await api.getSession(sessionId);
            setProgress(session.progress);
            setCurrentExercise(session.current_exercise);
          } catch {
            setErrorMessage({ code: err.code, message: "Session is no longer active." });
          }
        } else {
          setErrorMessage({ code: err.code, message: err.message });
        }
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  // Advance to next exercise or show completion
  const handleContinue = async () => {
    if (!answerResult || !sessionId) return;

    // Check for failure (out of hearts)
    if (answerResult.failure_reason === "out_of_hearts") {
      setShowOutOfHeartsModal(true);
      return;
    }

    // Check for lesson completion
    if (answerResult.rewards) {
      setCompletedRewards(answerResult.rewards);
      queryClient.invalidateQueries({ queryKey: queryKeys.path });
      queryClient.invalidateQueries({ queryKey: queryKeys.me });
      queryClient.invalidateQueries({ queryKey: queryKeys.leaderboard });
      return;
    }

    // Reset feedback and inputs
    setAnswerResult(null);
    resetExerciseInputs();

    // Fetch next authoritative exercise
    try {
      const nextEx = await api.getCurrentExercise(sessionId);
      setCurrentExercise(nextEx);
    } catch (err) {
      if (err instanceof ApiClientError && err.code === "SESSION_NOT_ACTIVE") {
        // Session ended
        try {
          const session = await api.getSession(sessionId);
          setProgress(session.progress);
        } catch {
          // Ignore secondary session fetch failure
        }
      }
    }
  };

  // Abandon and return to path
  const handleConfirmQuit = async () => {
    setIsQuitting(true);
    if (sessionId && progress?.status === "active") {
      try {
        await api.abandonSession(sessionId);
      } catch {
        // Ignore if already abandoned
      }
    }
    queryClient.invalidateQueries({ queryKey: queryKeys.path });
    queryClient.invalidateQueries({ queryKey: queryKeys.me });
    startTransition(() => {
      router.push("/");
    });
  };

  // Refill hearts for 350 gems
  const handleRefillHearts = async () => {
    setIsRefilling(true);
    setRefillError(null);
    try {
      const res = await api.refillHearts();
      setHearts(res.hearts);
      setShowOutOfHeartsModal(false);
      setAnswerResult(null);
      queryClient.invalidateQueries({ queryKey: queryKeys.me });
      queryClient.invalidateQueries({ queryKey: queryKeys.path });
      // Re-initialize lesson now that learner has full hearts
      setInitTrigger((t) => t + 1);
    } catch (err) {
      if (err instanceof ApiClientError) {
        setRefillError(err.message);
      } else {
        setRefillError("Failed to refill hearts.");
      }
    } finally {
      setIsRefilling(false);
    }
  };

  // Render Lesson Complete Screen if finished
  if (completedRewards) {
    return (
      <LessonCompleteScreen
        rewards={completedRewards}
        onFinish={() => {
          startTransition(() => {
            router.push("/");
          });
        }}
      />
    );
  }

  // Loading state
  if (isLoading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-surface p-4">
        <div className="h-12 w-12 animate-spin rounded-full border-4 border-line border-t-brand" />
        <p className="mt-4 text-sm font-black uppercase tracking-wider text-ink-soft">
          Loading lesson...
        </p>
      </div>
    );
  }

  // Error state
  if (errorMessage) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-surface p-4">
        <ErrorState
          code={errorMessage.code}
          message={errorMessage.message}
          onRetry={() => {
            setIsLoading(true);
            setInitTrigger((t) => t + 1);
          }}
        />
        <button
          type="button"
          onClick={() => router.push("/")}
          className="mt-4 text-sm font-black uppercase tracking-wider text-ink-soft hover:text-ink"
        >
          ← Return to Learning Path
        </button>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen flex-col bg-surface pb-32">
      {/* Top Header */}
      <LessonHeader
        progress={progress}
        hearts={hearts}
        onQuit={() => setShowQuitModal(true)}
      />

      {/* Main Exercise Area */}
      <main
        className={`mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center px-4 py-8 ${
          answerResult && !answerResult.correct ? "animate-shake" : ""
        }`}
      >
        {currentExercise && (
          <>
            {currentExercise.type === "multiple_choice" && (
              <MultipleChoiceExercise
                prompt={currentExercise.prompt}
                payload={currentExercise.payload}
                selectedOptionId={mcOptionId}
                onSelect={setMcOptionId}
                disabled={Boolean(answerResult) || isSubmitting}
                isGraded={Boolean(answerResult)}
                isCorrect={answerResult?.correct}
              />
            )}

            {currentExercise.type === "word_bank" && (
              <WordBankExercise
                prompt={currentExercise.prompt}
                payload={currentExercise.payload}
                selectedTileIds={wbTileIds}
                onSelectTile={(tileId) => setWbTileIds((prev) => [...prev, tileId])}
                onRemoveTile={(tileId) => setWbTileIds((prev) => prev.filter((id) => id !== tileId))}
                disabled={Boolean(answerResult) || isSubmitting}
              />
            )}

            {currentExercise.type === "matching_pairs" && (
              <MatchingPairsExercise
                prompt={currentExercise.prompt}
                payload={currentExercise.payload}
                pairs={mpPairs}
                selectedLeftId={mpSelectedLeft}
                selectedRightId={mpSelectedRight}
                onSelectLeft={handleSelectLeft}
                onSelectRight={handleSelectRight}
                onUnpair={handleUnpair}
                disabled={Boolean(answerResult) || isSubmitting}
              />
            )}

            {currentExercise.type === "fill_blank" && (
              <FillBlankExercise
                prompt={currentExercise.prompt}
                payload={currentExercise.payload}
                selectedText={fbText}
                onSelectText={setFbText}
                disabled={Boolean(answerResult) || isSubmitting}
                isGraded={Boolean(answerResult)}
                isCorrect={answerResult?.correct}
              />
            )}

            {currentExercise.type === "type_answer" && (
              <TypeAnswerExercise
                prompt={currentExercise.prompt}
                payload={currentExercise.payload}
                text={taText}
                onChangeText={setTaText}
                disabled={Boolean(answerResult) || isSubmitting}
              />
            )}
          </>
        )}
      </main>

      {/* Bottom Feedback Sheet & Check Action */}
      <FeedbackSheet
        canCheck={canCheck}
        isSubmitting={isSubmitting}
        result={answerResult}
        onCheck={handleSubmitAnswer}
        onContinue={handleContinue}
      />

      {/* Confirmation Modal to Quit Session */}
      <QuitModal
        isOpen={showQuitModal}
        onClose={() => setShowQuitModal(false)}
        onConfirmQuit={handleConfirmQuit}
        isQuitting={isQuitting}
      />

      {/* Out of Hearts Modal */}
      <OutOfHeartsModal
        isOpen={showOutOfHeartsModal}
        hearts={hearts}
        gems={gems}
        onRefill={handleRefillHearts}
        onQuit={() => {
          setShowOutOfHeartsModal(false);
          startTransition(() => {
            router.push("/");
          });
        }}
        isRefilling={isRefilling}
        refillError={refillError}
      />
    </div>
  );
}
