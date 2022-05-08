## markdown_awesome

Imports data from the [awesome-selfhosted](https://github.com/awesome-selfhosted/awesome-selfhosted) markdown format.


```bash
$ git clone https://github.com/awesome-selfhosted/awesome-selfhosted
$ git clone https://github.com/awesome-selfhosted/awesome-selfhosted-data
$ hecat import --importer markdown_awesome --source-file awesome-selfhosted/README.md --output-directory awesome-selfhosted-data
```

In addition to the [list item format]([markdown format](https://github.com/awesome-selfhosted/awesome-selfhosted/blob/master/.github/PULL_REQUEST_TEMPLATE.md), the importer assumes a few things about the original markdown file:
- all level 3 (`###`) titles/sections contain the actual list data/items, other sections must use level 2 headings
- the list of licenses is available in a `## List of Licenses` section


If the source/destination directories are `git` repositories, and you want to import the original authors/committers list (`git log`) to the destination directory, you must do so manually. This will let `hecat` generate an `AUTHORS.md` retaining all contributors from the original repo:

```bash
SOURCE_REPO=../awesome-selfhosted
DEST_REPO=../awesome-selfhosted-data
# copy the orignal .mailmap to the new repository
cp $SOURCE_REPO/.github/.mailmap $DEST_REPO/.mailmap
# place the .mailmap at the standard location in the source repository
cp $SOURCE_REPO/.github/.mailmap $SOURCE_REPO/.mailmap
# generate a git log to use as a template for the new' "dummy" commit log
git -C $SOURCE_REPO log --reverse --format="%ai;%aN;%aE;%s" | tee -a history.log
# create an orphan branch in the target repository, to hold all dummy commits
git -C $DEST_REPO checkout --orphan import-git-history
# create a dummy/empty commit for each commit in the original log (preserving author and date)
cat history.log | while read -r line; do date=$(echo "$line" | awk -F';' '{print $1}'); author=$(echo "$line" | awk -F';' '{print $2}'); email=$(echo "$line" | awk -F';' '{print $3}'); message=$(echo "$line" | awk -F';' '{print $4}'); git -C $DEST_REPO commit --allow-empty --author="$author <$email>" --date="$date" --message="$message"; done
# merge the orphan branch/dummy commit history to your main branch
git -c $DEST_REPO checkout master
git -c $DEST_REPO merge --allow-unrelated-histories import-git-history
```
