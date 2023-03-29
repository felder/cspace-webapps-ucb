#!/usr/bin/env bash

# create a merritt manifest file and POST it to merrit ingest

source step1_set_env.sh || { echo 'could not set environment vars. is step1_set_env.sh available?'; exit 1; }

RUN_DATE=`date +%Y%m%d%H%M`
TIFFS=$1
TIFFS_ERRORS="${TIFFS/tiffs/not_tiffs}"
TIFFS_QUEUED="${TIFFS/tiffs/queued}"
MANIFEST="${TIFFS/tiffs.csv/checkm}"
rm -f ${TIFFS_ERRORS} ; touch ${TIFFS_ERRORS}
rm -f ${TIFFS_QUEUED} ; touch ${TIFFS_QUEUED}
rm -f ${MANIFEST} ; touch ${MANIFEST}

# these are set outside the script (i.e. by step1_set_env.sh)
# as environment variables
S3BUCKET="${S3BUCKET}"
SUBMITTER="${SUBMITTER}"
MERRITT_INGEST=${MERRITT_INGEST}
collection_username="${COLLECTION_USERNAME}"
collection_password="${COLLECTION_PASSWORD}"

cp template.checkm ${MANIFEST}

for TIFF in `cut -f1 ${TIFFS}`
  do
    if [[ ! "${TIFF}" =~ TIF ]]; then
      echo "${TIFF} does not have TIF in it; diverting to error queue"
      echo -e "${TIFF}\t${RUN_DATE}" >> ${TIFFS_ERRORS}
    fi
    #%fields | nfo:fileUrl | nfo:hashAlgorithm | nfo:hashValue | nfo:fileSize | nfo:fileLastModified | nfo:fileName | mrt:primaryIdentifier | mrt:localIdentifier | mrt:creator | mrt:title | mrt:date
    ACCESSION_NUMBER="${TIFF/_*/}"
    echo "${ACCESSION_NUMBER}"
    TITLE=`./check_db.sh "${ACCESSION_NUMBER}" metadata`
    # get rid of all vertical bars in the data
    TITLE=${TITLE/|/, }
    echo "${TITLE}"
    echo "${S3BUCKET}/${TIFF} | | | | | | | ${TIFF} | UC/JEPS Herbaria | ${TITLE} |" >> ${MANIFEST}
    echo -e "${TIFF}\t${RUN_DATE}" >> ${TIFFS_QUEUED}
done
echo "#%eof" >> ${MANIFEST}

wc -l ${TIFFS}
wc -l ${TIFFS_QUEUED}
wc -l ${TIFFS_ERRORS}
wc -l ${MANIFEST}
echo "submitting to merritt, `date`"

# -F "profile=ucjeps_img_archive" \
# -F "profile=merritt_demo_content" \
#curl --verbose -u jblowe:2t0L59PRB472 \
curl --verbose -u ${collection_username}:${collection_password} \
-F "file=@${MANIFEST}" \
-F "type=container-batch-manifest" \
-F "submitter=${SUBMITTER}" \
-F "responseForm=xml" \
-F "profile=ucjeps_img_archive_content" \
${MERRITT_INGEST}

