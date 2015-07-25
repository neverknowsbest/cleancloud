import boto

GLOBAL_BUCKETS = {}

def get_s3_bucket(bucket):
	"""Get s3 bucket by reading the s3 bucket cache or opening a new connection"""
	if bucket not in GLOBAL_BUCKETS:
		s3 = boto.connect_s3()
		s3_bucket = s3.create_bucket(bucket)
		GLOBAL_BUCKETS[bucket] = s3_bucket
		s3.close()
	else:
		s3_bucket = GLOBAL_BUCKETS[bucket]
		
	return s3_bucket	

def get_string_from_s3(bucket, s3filename):
	"""Get string from S3 bucket bucket, with S3 filename s3filename."""
	s3_bucket = get_s3_bucket(bucket)
	file_list = s3_bucket.list(s3filename)

	contents = []
	for k in file_list:
		contents.append(k.get_contents_as_string())
	contents = ''.join(contents)
	
	return contents		

def save_string_to_s3(contents, bucket, filename, public=False):
	"""Save string in contents to S3 bucket bucket, with S3 filename filename. If public is True, the file is publicly accessible."""
	s3_bucket = get_s3_bucket(bucket)
	k = Key(s3_bucket)
	k.key = filename
	k.set_contents_from_string(contents)
	if public:
		k.set_acl('public-read')