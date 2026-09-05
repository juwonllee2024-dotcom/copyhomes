# Product research — 2026-09-05

## Problem

People still use repeated `Save As` when the same working file belongs in a
backup folder, a share folder, and a project folder. A long-running forum
question describes opening each folder separately and saving the file again:
<https://forums.tomshardware.com/threads/how-can-i-save-one-file-in-multiple-folders.1004918/>.
A 2026 productivity discussion repeats the desire to save one file in several
places: <https://www.reddit.com/r/ProductivityApps/comments/1sxkhkd/whats_one_simple_desktop_task_that_still_feels/>.

## Alternatives and gap

- Syncthing provides continuous multi-device synchronization, watchers, block
  indexes, and conflict behavior:
  <https://docs.syncthing.net/users/syncing>.
- FreeFileSync provides folder comparison, synchronization settings, previews,
  and batch jobs:
  <https://freefilesync.org/manual.php>.
- `rsync` is a powerful one-way copy primitive, but leaves the user to design
  destination policy and rollback:
  <https://rsync.samba.org/documentation.html>.

The narrow hypothesis is not “replace sync.” It is: when a person intentionally
wants one file in two or three local places, a one-shot, preview-first,
hash-verified, undoable action is easier to trust than configuring a sync
system.

## Candidate test

First ten users: Windows developers, designers, and students who keep a backup
or share copy. Reach them through targeted GitHub issues/discussions and
relevant community posts, without paid promotion or spam.

Seven-day experiment: ask ten people to run `copyhomes plan` on a real file,
then measure how many complete `save` plus `undo` without help. Continue only
if at least eight can understand the preview and no test loses or silently
overwrites a file.

## Business hypothesis

Free MIT core remains useful alone. A future paid layer could offer signed
desktop installers, team policy packs, or support automation; willingness to
pay is unverified. No paid service is required for the MVP.
