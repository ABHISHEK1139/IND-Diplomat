"use client";

import { motion } from "framer-motion";

interface GlassCardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
  onClick?: () => void;
}

export default function GlassCard({ children, className = "", hover = true, onClick }: GlassCardProps) {
  return (
    <motion.div
      whileHover={hover ? { y: -2, scale: 1.01 } : undefined}
      transition={{ duration: 0.2 }}
      onClick={onClick}
      className={`glass p-5 cursor-pointer transition-shadow hover:shadow-[0_8px_32px_rgba(59,130,246,0.08)] ${className}`}
    >
      {children}
    </motion.div>
  );
}
