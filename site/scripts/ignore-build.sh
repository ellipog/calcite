#!/bin/sh
# Vercel's ignored build step (vercel.json, CAL-230): exits 0, which skips the build, when nothing
# the site is built from changed since this branch's last deploy, and 1, which builds, when
# something did or when it can't tell. What it's built from is site/ and what it reads of the rest
# of the repo (README.md, "Where each page comes from"). docs/decisions.md, which nearly every
# commit adds to, only names the decisions a page cites, and a page that cites a new one changes
# itself, so the log alone doesn't build. Vercel runs this in site/, with the commit checked out.

base="${VERCEL_GIT_PREVIOUS_SHA:-}"
if [ -z "$base" ] || ! git cat-file -e "$base^{commit}" 2>/dev/null; then
	echo "No earlier deploy to compare with here, so it builds."
	exit 1
fi
if git diff --quiet "$base" HEAD -- . ../README.md ../docs/guide ../docs/pregen.md ../docs/PLAN.md \
	../bench/results ../bench/README.md ../cases ../plugins ../rig/differences ../src/server/config.calx; then
	echo "Nothing the site is built from changed since $base, so it doesn't build."
	exit 0
fi
echo "What the site is built from changed since $base, so it builds."
exit 1
