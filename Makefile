SHELL := /bin/bash

.PHONY: help # generate list of targets with descriptions
help:
	@echo "USAGE: make TARGET"
	@echo "Available targets:"
	@grep '^.PHONY: .* #' Makefile | sed 's/\.PHONY: \(.*\) # \(.*\)/\1	\2/' | expand -t20

.PHONY: clean # clean files generated by make install/test_run
clean:
	-rm -rf build/ dist/ hecat.egg-info/ tests/awesome-selfhosted tests/awesome-selfhosted-data tests/audio/ tests/video/ tests/shaarli.yml tests/html-table hecat.log tests/awesome-selfhosted-html tests/requirements.txt trivy trivy_*_Linux-64bit.tar.gz tests/webpages/ tests/github-stars-backup.yml

# do not install sphinx from setup.py/install_requires, workaround for https://github.com/sphinx-doc/sphinx/issues/11130
.PHONY: install # install in a virtualenv
install:
	python3 -m venv .venv && source .venv/bin/activate && \
	pip3 install wheel && \
	python3 -m pip install .

##### TESTS #####

.PHONY: test # run tests
test: test_pylint clean test_import_shaarli test_download_video test_download_audio test_export_html_table clone_awesome_selfhosted test_import_awesome_selfhosted test_process_awesome_selfhosted test_awesome_lint test_export_awesome_selfhosted_md test_export_awesome_selfhosted_html test_archive_webpages scan_trivy import_github_stars_backup

.PHONY: test_short # run tests except those that consume github API requests/long URL checks
test_short: test_pylint clean test_import_shaarli test_archive_webpages test_download_video test_download_audio test_export_html_table clone_awesome_selfhosted test_awesome_lint test_export_awesome_selfhosted_md test_export_awesome_selfhosted_html import_github_stars_backup

.PHONY: test_pylint # run linter (non blocking)
test_pylint: install
	source .venv/bin/activate && \
	pip3 install pylint pyyaml && \
	pylint --errors-only --disable=too-many-locals,line-too-long,consider-using-f-string hecat
	-source .venv/bin/activate && \
	pylint --disable=too-many-locals,line-too-long,consider-using-f-string hecat

.PHONY: clone_awesome_selfhosted # clone awesome-selfhosted/awesome-selfhosted-data
clone_awesome_selfhosted:
	git clone --depth=1 https://github.com/awesome-selfhosted/awesome-selfhosted tests/awesome-selfhosted
	git clone https://github.com/awesome-selfhosted/awesome-selfhosted-data tests/awesome-selfhosted-data

.PHONY: test_import_awesome_selfhosted # test import from awesome-sefhosted
test_import_awesome_selfhosted: install
	rm -rf tests/awesome-selfhosted-data/{tags,software,platforms}
	mkdir tests/awesome-selfhosted-data/{tags,software,platforms}
	source .venv/bin/activate && \
	hecat --config tests/.hecat.import_awesome_selfhosted.yml && \
	hecat --config tests/.hecat.import_awesome_selfhosted_nonfree.yml

.PHONY: test_import_github_stars_backup # test import from github-stars-backup
test_import_github_stars_backup: install
	rm -f tests/github-stars-backup.yml
	source .venv/bin/activate && \
	hecat --config tests/.hecat.import_github_stars_backup.yml

.PHONY: test_process_awesome_selfhosted # test all processing steps on awesome-selfhosted-data
test_process_awesome_selfhosted: install test_url_check test_update_github_metadata test_awesome_lint
	cd tests/awesome-selfhosted-data && git --no-pager diff --color=always

.PHONY: test_url_check # test URL checker on awesome-sefhosted-data
test_url_check: install
	source .venv/bin/activate && \
	hecat --config tests/.hecat.url_check.yml

.PHONY: test_update_github_metadata # test github metadata updater/processor on awesome-selfhosted-data
test_update_github_metadata: install
	source .venv/bin/activate && \
	hecat --config tests/.hecat.github_metadata.yml

.PHONY: test_awesome_lint # test linter/compliance checker on awesome-sefhosted-data
test_awesome_lint: install
	source .venv/bin/activate && \
	hecat --config tests/.hecat.awesome_lint.yml

.PHONY: test_export_awesome_selfhosted_md # test export to singlepage markdown from awesome-selfhosted-data
test_export_awesome_selfhosted_md: install
	source .venv/bin/activate && \
	hecat --config tests/.hecat.export_markdown_singlepage.yml && \
	cd tests/awesome-selfhosted && git --no-pager diff --color=always

.PHONY: test_export_awesome_selfhosted_html # test export to singlepage HTML from awesome-selfhosted-data
test_export_awesome_selfhosted_html: install
	rm -rf tests/awesome-selfhosted-html
	mkdir -p tests/awesome-selfhosted-html
	source .venv/bin/activate && \
	hecat --config tests/.hecat.export_markdown_multipage.yml && \
	sed -i 's|<a href="https://github.com/pradyunsg/furo">Furo</a>|<a href="https://github.com/nodiscc/hecat/">hecat</a>, <a href="https://www.sphinx-doc.org/">sphinx</a> and <a href="https://github.com/pradyunsg/furo">furo</a>. Content under <a href="https://github.com/awesome-selfhosted/awesome-selfhosted-data/blob/master/LICENSE">CC-BY-SA 3.0</a> license.|' .venv/lib/python*/site-packages/furo/theme/furo/page.html && \
	sphinx-build -b html -c tests/ -d tests/awesome-selfhosted-html/.doctrees tests/awesome-selfhosted-html/md/ tests/awesome-selfhosted-html/html/
	# remove unused files for static site publication
	rm tests/awesome-selfhosted-html/html/.buildinfo tests/awesome-selfhosted-html/html/objects.inv

.PHONY: test_export_github_stars_backup_html # test export to singlepage HTML from awesome-selfhosted-data
test_export_github_stars_backup_html: install
	rm -rf tests/github-stars-backup-html
	mkdir -p tests/github-stars-backup-html
	source .venv/bin/activate && \
	hecat --config tests/.hecat.export_github_stars_backup_multipage.yml && \
	sed -i 's|<a href="https://github.com/pradyunsg/furo">Furo</a>|<a href="https://github.com/nodiscc/hecat/">hecat</a>, <a href="https://www.sphinx-doc.org/">sphinx</a> and <a href="https://github.com/pradyunsg/furo">furo</a>. Content under <a href="https://github.com/awesome-selfhosted/awesome-selfhosted-data/blob/master/LICENSE">CC-BY-SA 3.0</a> license.|' .venv/lib/python*/site-packages/furo/theme/furo/page.html && \
	sphinx-build -b html -c tests/ -d tests/github-stars-backup-html/.doctrees tests/github-stars-backup-html/md/ tests/github-stars-backup-html/html/
	# remove unused files for static site publication
	rm tests/github-stars-backup-html/html/.buildinfo tests/github-stars-backup-html/html/objects.inv


.PHONY: test_import_shaarli # test import from shaarli JSON
test_import_shaarli: install
	source .venv/bin/activate && \
	hecat --config tests/.hecat.import_shaarli.yml

.PHONY: test_download_video # test downloading videos from the shaarli import, test log file creation
test_download_video: install
	rm -f tests/hecat.log
	source .venv/bin/activate && \
	hecat --log-file tests/hecat.log --config tests/.hecat.download_video.yml
	grep -q 'writing data file tests/shaarli.yml' tests/hecat.log

.PHONY: test_download_audio # test downloading audio files from the shaarli import
test_download_audio: install
	source .venv/bin/activate && \
	hecat --config tests/.hecat.download_audio.yml

.PHONY: test_archive_webpages # test webpage archiving
test_archive_webpages: install
	mkdir -p tests/webpages
	# create directory that should be removed by clean_removed
	mkdir -p tests/webpages/public/9999999999
	source .venv/bin/activate && \
	hecat --log-level DEBUG --config tests/.hecat.archive_webpages.yml
	# test existence and content of archived page
	@grep -q 'Template Designer Documentation' tests/webpages/public/8351/jinja.palletsprojects.com/en/latest/templates/index.html
	# test that directories were effectively removed
	@if [[ -d tests/webpages/public/9999999999 ]]; then echo "ERROR tests/webpages/public/9999999999 should have been removed by clean_removed: True"; exit 1; fi
	@if [[ -d tests/webpages/public/6625 ]]; then echo "ERROR tests/webpages/public/6625 should have been removed by clean_excluded: True"; exit 1; fi


.PHONY: test_export_html_table # test exporting shaarli data to HTML table
test_export_html_table: test_import_shaarli install
	mkdir -p tests/html-table
	source .venv/bin/activate && \
	hecat --config tests/.hecat.export_html_table.yml

TRIVY_VERSION=0.44.0
TRIVY_EXIT_CODE=1
.PHONY: scan_trivy # run trivy vulnerability scanner
scan_trivy:
	source .venv/bin/activate && pip3 freeze --local > tests/requirements.txt
	wget --quiet --continue -O trivy_$(TRIVY_VERSION)_Linux-64bit.tar.gz https://github.com/aquasecurity/trivy/releases/download/v$(TRIVY_VERSION)/trivy_$(TRIVY_VERSION)_Linux-64bit.tar.gz
	tar -z -x trivy -f trivy_$(TRIVY_VERSION)_Linux-64bit.tar.gz
	./trivy --exit-code $(TRIVY_EXIT_CODE) fs tests/requirements.txt
