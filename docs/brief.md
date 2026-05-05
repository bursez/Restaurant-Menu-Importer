# AI Project: Restaurant Menu Importer

## 🎯 Goal

Develop an application that reads a restaurant menu from a **web page** or from
**free text** (pasted by the user), analyses it with an AI model, and produces
a **structured JSON** with the dishes, categories, prices, and descriptions.

**Platform-free** project: the team can choose the preferred platform
(web app, console, desktop, mobile). The AI/ML library is also free to choose.

---

## 🧠 Problem to solve

Restaurant menus on the web exist in hundreds of different formats: non-uniform HTML
pages, scanned PDFs, Instagram posts, Word files. Aggregators such as TheFork
or Google Maps must "extract" structure from unstructured text.

This project is an **intelligent extractor**: given a menu in any text format,
it produces a canonical, usable JSON for any management system.

---

## 🛠️ Technical Specifications

### Accepted inputs

- URL of a web page containing the restaurant menu (scraping + text extraction)
- Free text pasted by the user (copy-paste from PDF or Word)
- `.txt` or `.md` files

### Expected JSON output

```json
{
  "restaurant": "Trattoria da Mario",
  "currency": "EUR",
  "categories": [
    {
      "name": "Starters",
      "items": [
        {
          "name": "Bruschetta al pomodoro",
          "description": "Toasted bread with fresh tomato and basil",
          "price": 6.50,
          "allergens": ["gluten"],
          "tags": ["vegetarian"]
        }
      ]
    },
    {
      "name": "First Courses",
      "items": [ ... ]
    }
  ]
}
```

### Processing pipeline

```
URL / Text
    │
    ▼
┌─────────────────────────┐
│  Fetch & Clean          │  HTTP GET + strip HTML tags (if URL)
│                         │  Or accepts raw text
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│  AI Extraction          │  Prompt to an LLM via API (OpenAI / local Ollama)
│                         │  or local NER model (Hugging Face / ML.NET)
│  Suggested prompt:      │
│  "Extract the menu from │
│  the following text and │
│  return JSON in the     │
│  format [schema]..."    │
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│  Validation & Cleanup   │  Validate JSON, normalise prices (comma → dot)
│                         │  Category deduplication, text trimming
└─────────────────────────┘
    │
    ▼
┌─────────────────────────┐
│  Output                 │  JSON to file / clipboard / API response
└─────────────────────────┘
```

### AI integration — options

The team chooses one of the following:

| Option | Cost | Offline |
|---|---|---|
| OpenAI API (`gpt-4o-mini`) | ~$0.001/menu | No |
| Local Ollama (`llama3.2:3b`) | Free | Yes |
| HuggingFace Inference API | Free tier | No |
| ML.NET + custom ONNX model | Free | Yes |

The choice must be documented in the README with justification.

### Minimum requirements

1. Works with at least 5 different real restaurant menus (to be included as test cases)
2. Produces valid JSON conforming to the schema in every case
3. Handles texts in **Italian** and **English**
4. Handles missing prices (`null` field, not an error)
5. Minimal user interface (web form, CLI with arguments, or desktop form)

---

## 📦 Expected Output

- Working application on the chosen platform
- At least 5 test cases with real menus (URL or text file) and expected JSON
- README with: chosen platform, AI stack, execution instructions
- Qualitative accuracy evaluation on a set of 10 menus

## 📚 References

- OpenAI structured output: https://platform.openai.com/docs/guides/structured-outputs
- Ollama (local LLM): https://ollama.com
- JSON Schema for output validation