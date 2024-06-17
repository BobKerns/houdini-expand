# Houdini HDA filter

This tool will enable Houdini HDA's to be compared and merged, stored as text files. It uses Houdini's `hota` command line tool if it's available. It also stores the original `.hda` file in `git-lfs` if that's configured, which allows repositories with only git-lfs and this tool to check out .hda files even if Houdini is not installed.

## Configuration

```bash
git_hooks/hda_filter.py install [install_dir]
````

## Operation

