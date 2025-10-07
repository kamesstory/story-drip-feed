# Story Chunking Test Scripts

Test the chunking system with various stories to verify behavior.

## Quick Test Scripts

### Test Single Story

```bash
# Test with default (pale-lights example, agent chunker)
./test_story.sh

# Test with specific story
./test_story.sh examples/inputs/dragons-example-1.txt

# Test with simple chunker (no AI)
./test_story.sh examples/inputs/pale-lights-example-1.txt simple
```

### Test All Examples

```bash
poetry run python test_all_examples.py
```

This will:
- Test all `.txt` files in `examples/inputs/`
- Show chunk distribution and statistics
- Generate detailed reports

### Test Multi-Chunk with Recaps

```bash
poetry run python test_multi_chunk.py
```

Creates an artificial long story (3x pale-lights) to test:
- Multi-chunk splitting
- Recap generation
- Scene break detection

## Test Output

All tests create:
- `./local_data/` - Story files, chunks, manifests
- `./test_stories.db` - SQLite database with records

### Directory Structure

```
local_data/
├── raw/story_000001/
│   ├── metadata.yaml          # Title, author, extraction info
│   ├── content.txt             # Clean story text
│   └── original_email.txt      # Original for debugging
└── chunks/story_000001/
    ├── chunk_manifest.yaml     # Chunk metadata
    ├── chunk_001.txt           # First chunk
    ├── chunk_002.txt           # Second chunk (with recap)
    └── ...
```

## Understanding Results

### Chunk Counts

- **1 chunk**: Stories < ~7,000 words usually stay together
- **2 chunks**: Stories ~14,000-16,000 words with good scene break
- **3+ chunks**: Very long stories (20,000+ words)

### Recap Overhead

Each chunk after the first includes a "Previously:" recap (~250 words). For example:

- Original story: 21,290 words
- With recaps: 21,838 words
- Overhead: 548 words (2.6%)

### Agent Decisions

The agent looks for:
1. **Explicit scene breaks** (`---`, `* * *`, `═══`) - ALWAYS respected
2. **Natural transitions** (location/time changes, scene endings)
3. **Completed arcs** (after conflict resolution, not during)

It avoids:
- Mid-combat breaks
- Mid-dialogue breaks
- Mid-emotional arc breaks

## Custom Tests

Create your own test by adding `.txt` files to `examples/inputs/`:

```bash
# Add your story
cp your-story.txt examples/inputs/

# Test it
./test_story.sh examples/inputs/your-story.txt
```

## Troubleshooting

**"Too short" errors**: Stories need at least 100 words

**Agent errors**: Make sure Claude Code desktop app is running and `claude-agent-sdk` is installed:
```bash
poetry install
```

**No chunks created**: Check that story has proper paragraph breaks (double newlines)
