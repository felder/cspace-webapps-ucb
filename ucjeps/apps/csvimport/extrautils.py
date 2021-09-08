import csv
import logging
import datetime, time

from os import path, listdir, stat
from os.path import isfile, isdir, join
from xml.sax.saxutils import escape

from common import cspace  # we use the config file reading function
from common.utils import deURN
from cspace_django_site import settings

config = cspace.getConfig(path.join(settings.BASE_DIR, 'config'), 'csvimport')
QUEUEDIR = config.get('files', 'directory')
CODEPATH = path.join(settings.BASE_DIR, 'csvimport')
SERVERLABEL = config.get('info', 'serverlabel')
SERVERLABELCOLOR = config.get('info', 'serverlabelcolor')
INSTITUTION = config.get('info', 'institution')
FIELDS2WRITE = 'job filename handling status'.split(' ')
BATCHPARAMETERS = 'None'

if isdir(QUEUEDIR):
    IMPORTDIR_MSG = "Using %s as working directory for csvimport files" % QUEUEDIR
else:
    IMPORTDIR_MSG = "%s is not an existing directory, using /tmp instead for csvimport files" % QUEUEDIR
    QUEUEDIR = '/tmp'
    # raise Exception("csvImport working directory %s does not exist. this webapp will not work without it!" % QUEUEDIR)

JOBDIR = path.join(QUEUEDIR, '%s')

# Get an instance of a logger, log some startup info
logger = logging.getLogger(__name__)


def getJobfile(jobnumber):
    return JOBDIR % jobnumber

priority =   'input counted validated added updated undo inprogress'.split(' ')
# we need to adjust certain line counts to account for headers
adjustments = {'input': 1, 'count': 1, 'valid': 1, 'invalid': 1, 'add': 1, 'update': 1, 'undo': 1, 'terms': 0}
next_steps = 'count,validate,import,undo,undo,none,in progress'.split(',')

def jobsummary(jobstats):
    results = [0, 0, 0, '', 'completed']
    first_date = ''
    new_order = 0
    update_type = ''
    import_type = ''
    archived = False
    for i,(jobfile, status, count, lines, date_uploaded) in enumerate(jobstats):

        if date_uploaded > first_date:
            first_date = date_uploaded

        # adjust counts for csv to account for headers, if any (some files have 2!)
        if '.csv' in jobfile:
            try:
                revised_count = count - adjustments[status]
                if revised_count < 0: revised_count = 0
                jobstats[i][2] = revised_count
            except:
                pass

            if status in 'add update both'.split(' '):
                import_type = status

            continue

        if status in priority:
            order = priority.index(status)
            if order > new_order:
                new_order = order

        # if the job is archived...
        if status == 'archived':
            archived = True
            continue

    try:
        next = next_steps[new_order]
    except:
        next = 'unknown'

    if import_type != '' and next != 'undo' and next != 'in progress':
        next = import_type

    results[3] = first_date
    results[4] = next
    if results[2] > 0 and results[4] == 'completed':
        results[4] = 'problem'
    if archived:
        results[4] = 'archive'
        pass
    return results

def getJobParts(job_filename):
    parts = job_filename.split('.')
    try:
        file_type = parts[1]
    except:
        file_type = 'unknown'
    return (parts[0], file_type)

def getJoblist(request):
    if 'num2display' in request.POST:
        num2display = int(request.POST['num2display'])
    else:
        num2display = 300

    jobpath = JOBDIR % ''
    filelist = [f for f in listdir(jobpath) if isfile(join(jobpath, f))]
    archived = [getJobParts(f)[0] for f in filelist if 'archived' in f]
    jobdict = {}
    archive_dict = {}
    errors = []
    for f in sorted(filelist):

        (jobkey, file_type) = getJobParts(f)

        if jobkey in archived:
            linecount, records, date_uploaded = checkFile(join(jobpath, f), 'archived')
            archive_dict[jobkey] = [f, date_uploaded]
            continue

        if len(jobdict.keys()) > num2display:
            records = []
        else:
            # we only need to count lines if the file is within range...
            try:
                linecount, records, date_uploaded = checkFile(join(jobpath, f), 'current')
            except:
                # TODO: we skip files altogether if there is any problem processing them, probably we should do something better...
                continue
        if not jobkey in jobdict: jobdict[jobkey] = []
        jobdict[jobkey].append([f, file_type, linecount, records, date_uploaded])
    date_dict = {}
    for jobkey in jobdict.keys():
        max_date = ''
        for j in jobdict[jobkey]:
            if j[4] > max_date:
                max_date = j[4]
        date_dict[max_date] = jobkey
    joblist = [[date_dict[date], jobdict[date_dict[date]], jobsummary(jobdict[date_dict[date]])] for date in sorted(date_dict, reverse=True) if jobkey != '']
    num_jobs = len(joblist)
    return joblist[0:num2display], errors, num_jobs, len(errors), archive_dict


def checkFile(filename, check_type):
    file_handle = open(filename, 'r', encoding='utf-8')
    date_uploaded  = datetime.datetime.fromtimestamp(path.getmtime(filename)).strftime("%Y-%m-%d %H:%M:%S")
    if check_type == 'archived':
        lines = []
    else:
        lines = [l for l in file_handle.read().splitlines()]
    return len(lines), [], date_uploaded


def writeCsv(filename, items, writeheader):
    filehandle = open(filename, 'w', encoding='utf-8')
    writer = csv.writer(filehandle, delimiter='|')
    writer.writerow(writeheader)
    for item in items:
        row = []
        for x in writeheader:
            if x in item.keys():
                cell = str(item[x])
                cell = cell.strip()
                cell = cell.replace('"', '')
                cell = cell.replace('\n', '')
                cell = cell.replace('\r', '')
            else:
                cell = ''
            row.append(cell)
        writer.writerow(row)
    filehandle.close()


# this somewhat desperate function makes an html table from a tab- and newline- delimited string
def reformat(filecontent):
    result = deURN(filecontent)
    result = result.replace('\n','<tr><td>')
    result = result.replace('\t','<td>')
    result = result.replace('|','<td>')
    result = result.replace('False','<span class="error">False</span>')
    result += '</table>'
    return '<table width="100%"><tr><td>\n' + result
