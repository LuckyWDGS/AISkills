"""Separate composition experiment after size-only cases; two new prompts."""
import run_live as live

live.ROOT = live.ROOT / "prompt-shapes"
live.ROOT.mkdir(exist_ok=True)
live.CASES = [
    ("square_prompt", "1024x1024", "png", "IMPORTANT OUTPUT COMPOSITION: Generate a SQUARE image, aspect ratio exactly 1:1, equal canvas width and height. Use a square 1024 by 1024 pixel canvas. Arrange the scene in a compact centered composition appropriate to a square image. " + live.PROMPT, []),
    ("portrait_prompt", "1024x1536", "png", "IMPORTANT OUTPUT COMPOSITION: Generate a VERTICAL PORTRAIT image, aspect ratio exactly 2:3, height one and a half times the width. Use a 1024 pixel wide by 1536 pixel tall canvas. Compose the observatory, greenhouse, bridge and mountains in depth from the bottom foreground to the upper background to fit the tall canvas. " + live.PROMPT, []),
]
live.main()
