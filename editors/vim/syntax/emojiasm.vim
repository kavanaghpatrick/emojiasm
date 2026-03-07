" EmojiASM syntax file
" Language: EmojiASM (.emoji)
" Maintainer: EmojiASM project
" FileType: emojiasm

if exists("b:current_syntax")
  finish
endif

setlocal fileencoding=utf-8

syn match emojiComment    "💭.*$"
syn match emojiDirective  "^\s*\(📜\|🏷️\|🏷\)"
syn match emojiStack      "\(📥\|📤\|📋\|🔀\|🫴\|🔄\)"
syn match emojiArith      "\(➕\|➖\|✖️\|✖\|➗\|🔢\)"
syn match emojiCompare    "\(🟰\|📏\|📐\|🤝\|🤙\|🚫\)"
syn match emojiControl    "\(👉\|🤔\|😤\|📞\|📲\|🛑\|💤\)"
syn match emojiIO         "\(📢\|🖨️\|🖨\|💬\|🎤\|🔟\)"
syn match emojiMem        "\(💾\|📂\)"
syn region emojiString start=/"/ end=/"/ skip=/\\"/ oneline
syn region emojiString start=/'/ end=/'/ skip=/\\'/ oneline
syn region emojiString start=/«/ end=/»/ oneline

hi def link emojiComment    Comment
hi def link emojiDirective  Function
hi def link emojiStack      Keyword
hi def link emojiArith      Operator
hi def link emojiCompare    Operator
hi def link emojiControl    Statement
hi def link emojiIO         Special
hi def link emojiMem        Type
hi def link emojiString     String

let b:current_syntax = "emojiasm"
