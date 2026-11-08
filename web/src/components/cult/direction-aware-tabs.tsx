// Cult UI (MIT) · https://github.com/nolly-studio/cult-ui · registry/default/ui/direction-aware-tabs.tsx
"use client"

import { ReactNode, useMemo, useState } from "react"
import { AnimatePresence, motion, MotionConfig } from "motion/react"
import useMeasure from "react-use-measure"

import { cn } from "@/lib/utils"

type Tab = {
  id: number
  label: ReactNode
  content: ReactNode
}

interface OgImageSectionProps {
  tabs: Tab[]
  className?: string
  /** Outer container radius (e.g. `rounded-lg`) */
  rounded?: string
  /** Inner tab/bubble radius — should be outer radius minus container padding (~3px) */
  roundedInner?: string
  onChange?: () => void
}

function DirectionAwareTabs({
  tabs,
  className,
  rounded,
  roundedInner,
  onChange,
}: OgImageSectionProps) {
  const [activeTab, setActiveTab] = useState(0)
  const [direction, setDirection] = useState(0)
  const [isAnimating, setIsAnimating] = useState(false)
  const [ref, bounds] = useMeasure()

  const content = useMemo(() => {
    const activeTabContent = tabs.find((tab) => tab.id === activeTab)?.content
    return activeTabContent || null
  }, [activeTab, tabs])

  const handleTabClick = (newTabId: number) => {
    if (newTabId !== activeTab && !isAnimating) {
      const newDirection = newTabId > activeTab ? 1 : -1
      setDirection(newDirection)
      setActiveTab(newTabId)
      onChange ? onChange() : null
    }
  }

  const variants = {
    initial: (direction: number) => ({
      x: 300 * direction,
      opacity: 0,
      filter: "blur(4px)",
    }),
    active: {
      x: 0,
      opacity: 1,
      filter: "blur(0px)",
    },
    exit: (direction: number) => ({
      x: -300 * direction,
      opacity: 0,
      filter: "blur(4px)",
    }),
  }

  return (
    <div className="flex w-full flex-col items-start">
      <div
        className={cn(
          "shadow-inner-shadow flex max-w-full cursor-pointer space-x-1 overflow-x-auto rounded-full border border-rule bg-rule-soft px-[3px] py-[3.2px]",
          className,
          rounded
        )}
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleTabClick(tab.id)}
            className={cn(
              "relative flex shrink-0 items-center gap-2 rounded-full px-4 py-2 text-[14px] font-medium transition focus-visible:outline-2 focus-visible:outline-ink",
              activeTab === tab.id
                ? "text-sheet"
                : "text-ink-soft hover:text-ink",
              rounded ? roundedInner : undefined
            )}
            style={{ WebkitTapHighlightColor: "transparent" }}
          >
            {activeTab === tab.id && (
              <motion.span
                layoutId="bubble"
                className={cn(
                  "absolute inset-0 z-0 bg-ink",
                  rounded ? roundedInner : "rounded-full"
                )}
                transition={{ type: "spring", bounce: 0.19, duration: 0.4 }}
              />
            )}

            <span className="relative z-10 flex items-center gap-2">{tab.label}</span>
          </button>
        ))}
      </div>
      <MotionConfig transition={{ duration: 0.4, type: "spring", bounce: 0.2 }}>
        <motion.div
          className="relative mx-auto h-full w-full overflow-hidden"
          initial={false}
          animate={{ height: bounds.height }}
        >
          <div className="pt-6" ref={ref}>
            <AnimatePresence
              custom={direction}
              mode="popLayout"
              onExitComplete={() => setIsAnimating(false)}
            >
              <motion.div
                key={activeTab}
                variants={variants}
                initial="initial"
                animate="active"
                exit="exit"
                custom={direction}
                onAnimationStart={() => setIsAnimating(true)}
                onAnimationComplete={() => setIsAnimating(false)}
              >
                {content}
              </motion.div>
            </AnimatePresence>
          </div>
        </motion.div>
      </MotionConfig>
    </div>
  )
}
export { DirectionAwareTabs }
