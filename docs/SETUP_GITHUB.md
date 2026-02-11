# Setting Up Your GitHub Fork

## Step 1: Fork the Original Repository

1. Go to the original repository: https://github.com/nikhilgy/quickbooks-mcp-server
2. Click the **"Fork"** button in the top right
3. This creates a copy at: `https://github.com/celstnblacc/quickbooks-mcp-server`

## Step 2: Update Your Local Remote

After forking, update your local repository to point to your fork:

```bash
# Remove the original remote
git remote remove origin

# Add your fork as the new origin
git remote add origin https://github.com/celstnblacc/quickbooks-mcp-server.git

# Add the original as upstream (to pull updates later)
git remote add upstream https://github.com/nikhilgy/quickbooks-mcp-server.git

# Verify remotes
git remote -v
```

You should see:
```
origin    https://github.com/celstnblacc/quickbooks-mcp-server.git (fetch)
origin    https://github.com/celstnblacc/quickbooks-mcp-server.git (push)
upstream  https://github.com/nikhilgy/quickbooks-mcp-server.git (fetch)
upstream  https://github.com/nikhilgy/quickbooks-mcp-server.git (push)
```

## Step 3: Commit All Your Changes

```bash
# Stage all new files and changes
git add .

# Check what will be committed
git status

# Create commit with all improvements
git commit -m "Add comprehensive test suite with 470+ tests

- Implemented 10 missing test types (contract, error recovery, property-based, etc.)
- Added 19 test files with ~470 tests
- Created test runner scripts (run_tests.sh, run_mutation_tests.sh)
- Added comprehensive documentation (9 new MD files)
- Set up CI/CD with GitHub Actions
- Added mutation testing and multi-version testing (tox)
- Enhanced existing tests and documentation

See TEST_IMPLEMENTATION_SUMMARY.md for full details."
```

## Step 4: Push to Your Fork

```bash
# Push to your fork
git push -u origin master

# If you get an error about diverged branches, use:
# git push -u origin master --force-with-lease
```

## Step 5: (Optional) Create Pull Request to Original

If you want to contribute your improvements back to the original repo:

1. Go to your fork: `https://github.com/celstnblacc/quickbooks-mcp-server`
2. Click **"Contribute"** → **"Open pull request"**
3. Title: "Add comprehensive test suite with 470+ tests"
4. Description: Reference `TEST_IMPLEMENTATION_SUMMARY.md`
5. Submit the PR!

## Step 6: Keep Your Fork Synced (Future)

To pull updates from the original repository:

```bash
# Fetch updates from upstream
git fetch upstream

# Merge upstream changes into your master
git checkout master
git merge upstream/master

# Push updates to your fork
git push origin master
```

## Your Repository Structure

After pushing, your fork will have:

```
https://github.com/celstnblacc/quickbooks-mcp-server/
├── 19 test files (~470 tests)
├── 14 documentation files
├── Enhanced test runner scripts
├── CI/CD workflow (.github/workflows/)
├── Mutation testing setup
└── All original files + improvements
```

## Quick Commands Summary

```bash
# 1. Fork on GitHub (manual step)
# 2. Update remotes
git remote remove origin
git remote add origin https://github.com/celstnblacc/quickbooks-mcp-server.git
git remote add upstream https://github.com/nikhilgy/quickbooks-mcp-server.git

# 3. Commit changes
git add .
git commit -m "Add comprehensive test suite with 470+ tests"

# 4. Push to your fork
git push -u origin master
```

## Troubleshooting

**Error: "failed to push some refs"**
- Your fork is empty, use: `git push -u origin master --force-with-lease`

**Error: "remote origin already exists"**
- First remove it: `git remote remove origin`

**Want to rename branch master → main?**
```bash
git branch -m master main
git push -u origin main
```

## Benefits of This Approach

✅ **Your own version** - Complete control over your fork
✅ **Attribution** - Fork shows it's based on original
✅ **Contribute back** - Can create PRs to original
✅ **Stay updated** - Can pull upstream changes
✅ **Professional** - Standard open-source workflow

---

**Ready to start?** First step: Fork the repo on GitHub! 🚀
