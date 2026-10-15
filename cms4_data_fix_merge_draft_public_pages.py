"""
One-off data fix, run once against chryscms_local during the django-cms 3.11.11 -> 5.0.13
upgrade, BEFORE letting `migrate` apply cms.0037_merge_page_treenode.

That migration hard-assumes exactly one cms_page row per TreeNode. django-cms 3.x's publish
workflow instead kept TWO Page rows sharing one TreeNode (draft + public copy, each with its
own PageContent/placeholders/plugins) - there is no official django-cms migration that collapses
this pairing, since sites are assumed to already be on the cms4+ versioning model by then.

Verified against chryscms_local before running: of the 31 node_ids with 2 Page rows, all 31 had
byte-identical PageContent (title/redirect) and placeholder/plugin content between the draft and
public copy, except one node where the draft had one extra (unpublished) RstPlugin that the
public copy lacked. So keeping the lower page id ("draft") per pair and deleting the higher
("public") duplicate - after repointing/dropping every RESTRICT FK that referenced it
(PageContent, Placeholder/CMSPlugin + subclass tables, PageUrl, PageSitemapProperties incl. its
self-referential public_extension_id, PagePermission) - never loses real content.

Run via: run_local_cms.py shell -c "exec(open(r'cms4_data_fix_merge_draft_public_pages.py').read())"
Afterwards, djangocms_versioning has no Version rows for the pre-existing PageContent at all
(cms core's own migrations don't create any), so every page is invisible on the public site
until Version rows are backfilled - see the follow-up one-liner in the rung's commit message.
"""
from django.db import connection, transaction

cur = connection.cursor()

cur.execute("SELECT node_id, id FROM cms_page ORDER BY node_id, id")
from collections import defaultdict
by_node = defaultdict(list)
for node_id, pid in cur.fetchall():
    by_node[node_id].append(pid)

pairs = [(pids[0], pids[1]) for pids in by_node.values() if len(pids) == 2]
lo_ids = [p[0] for p in pairs]
hi_ids = [p[1] for p in pairs]
print("pairs:", len(pairs))
assert len(hi_ids) == len(set(hi_ids))

with transaction.atomic():
    cur.execute("SET FOREIGN_KEY_CHECKS=0")

    cur.execute("SELECT id FROM django_content_type WHERE app_label='cms' AND model='pagecontent'")
    pagecontent_ct = cur.fetchone()[0]

    fmt = ",".join(["%s"] * len(hi_ids))
    cur.execute(f"SELECT id, page_id FROM cms_pagecontent WHERE page_id IN ({fmt})", hi_ids)
    hi_pagecontents = cur.fetchall()
    hi_pc_ids = [r[0] for r in hi_pagecontents]
    print("hi pagecontent rows:", len(hi_pc_ids))

    if hi_pc_ids:
        fmt_pc = ",".join(["%s"] * len(hi_pc_ids))
        cur.execute(
            f"SELECT id FROM cms_placeholder WHERE content_type_id=%s AND object_id IN ({fmt_pc})",
            [pagecontent_ct] + hi_pc_ids,
        )
        hi_placeholder_ids = [r[0] for r in cur.fetchall()]
        print("hi placeholder rows:", len(hi_placeholder_ids))

        if hi_placeholder_ids:
            fmt_ph = ",".join(["%s"] * len(hi_placeholder_ids))
            cur.execute(f"SELECT id, plugin_type FROM cms_cmsplugin WHERE placeholder_id IN ({fmt_ph})", hi_placeholder_ids)
            hi_plugins = cur.fetchall()
            print("hi cmsplugin rows:", len(hi_plugins))

            plugin_tables = {
                "FilerImagePlugin": "cmsplugin_filer_image_filerimage",
                "FilerVideoPlugin": "cmsplugin_filer_video_filervideo",
                "FilerFilePlugin": "cmsplugin_filer_file_filerfile",
                "FilerFolderPlugin": "cmsplugin_filer_folder_filerfolder",
                "FilerTeaserPlugin": "cmsplugin_filer_teaser_filerteaser",
                "RstPlugin": "cmsplugin_rst_rstpluginmodel",
                "SimpleGalleryPlugin": "cmsplugin_simple_gallery_simplegallerypointer",
                "LinkPlugin": "djangocms_link_link",
                "RawHTMLPluginPublisher": "djangocms_rawhtml_rawhtmlplugindata",
                "SnippetPlugin": "djangocms_snippet_snippetptr",
                "TextPlugin": "djangocms_text_ckeditor_text",
                "JPlayerPlugin": "jplayer_jplayerintermediate",
                "AliasPlugin": "cms_aliaspluginmodel",
                "PlaceholderPlugin": "cms_placeholderreference",
            }
            by_type = defaultdict(list)
            for pid, ptype in hi_plugins:
                by_type[ptype].append(pid)
            for ptype, ids in by_type.items():
                table = plugin_tables.get(ptype)
                if table:
                    fmt_ids = ",".join(["%s"] * len(ids))
                    cur.execute(f"DELETE FROM {table} WHERE cmsplugin_ptr_id IN ({fmt_ids})", ids)
                else:
                    print("WARNING: no subclass table mapping for plugin_type", ptype, "- leaving subclass row (if any), will delete base row only")

            fmt_ph_ids = ",".join(["%s"] * len(hi_placeholder_ids))
            cur.execute(f"DELETE FROM cms_cmsplugin WHERE placeholder_id IN ({fmt_ph_ids})", hi_placeholder_ids)

            cur.execute(f"DELETE FROM cms_placeholder WHERE id IN ({fmt_ph_ids})", hi_placeholder_ids)

        cur.execute(f"DELETE FROM cms_pagecontent WHERE id IN ({fmt_pc})", hi_pc_ids)

    cur.execute("UPDATE djangocms_page_sitemap_pagesitemapproperties SET public_extension_id=NULL")
    cur.execute(f"DELETE FROM djangocms_page_sitemap_pagesitemapproperties WHERE extended_object_id IN ({fmt})", hi_ids)

    cur.execute(f"DELETE FROM cms_pageurl WHERE page_id IN ({fmt})", hi_ids)

    cur.execute(f"DELETE FROM cms_pagepermission WHERE page_id IN ({fmt})", hi_ids)

    cur.execute(f"DELETE FROM cms_page WHERE id IN ({fmt})", hi_ids)

    cur.execute("SET FOREIGN_KEY_CHECKS=1")

print("done")

cur.execute("SELECT COUNT(*) FROM cms_page")
print("remaining pages:", cur.fetchone())
cur.execute("SELECT node_id, COUNT(*) c FROM cms_page GROUP BY node_id HAVING c != 1")
print("nodes with != 1 page now:", cur.fetchall())
