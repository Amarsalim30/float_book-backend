
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
)

;


CREATE TABLE businesses (
	id SERIAL NOT NULL, 
	owner_id INTEGER NOT NULL, 
	business_name VARCHAR NOT NULL, 
	opening_cash NUMERIC(14, 2), 
	opening_float NUMERIC(14, 2), 
	onboarding_completed BOOLEAN NOT NULL, 
	onboarding_completed_at TIMESTAMP WITH TIME ZONE, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT businesses_pkey PRIMARY KEY (id), 
	CONSTRAINT businesses_owner_id_fkey FOREIGN KEY(owner_id) REFERENCES users (id), 
	CONSTRAINT uq_businesses_owner_id UNIQUE NULLS DISTINCT (owner_id)
)

;


CREATE TABLE ledger_entries (
	id SERIAL NOT NULL, 
	business_id INTEGER NOT NULL, 
	account_type VARCHAR NOT NULL, 
	entry_type VARCHAR NOT NULL, 
	amount NUMERIC(14, 2) NOT NULL, 
	description VARCHAR, 
	created_by INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	transaction_id INTEGER, 
	tracked_account_id INTEGER, 
	CONSTRAINT ledger_entries_pkey PRIMARY KEY (id), 
	CONSTRAINT fk_ledger_entries_tracked_account_id FOREIGN KEY(tracked_account_id) REFERENCES tracked_accounts (id), 
	CONSTRAINT ledger_entries_business_id_fkey FOREIGN KEY(business_id) REFERENCES businesses (id), 
	CONSTRAINT ledger_entries_created_by_fkey FOREIGN KEY(created_by) REFERENCES users (id), 
	CONSTRAINT ledger_entries_transaction_id_fkey FOREIGN KEY(transaction_id) REFERENCES transactions (id)
)

;


CREATE TABLE mpesa_messages (
	id SERIAL NOT NULL, 
	business_id INTEGER NOT NULL, 
	reference VARCHAR NOT NULL, 
	sender VARCHAR, 
	amount NUMERIC(14, 2) NOT NULL, 
	direction VARCHAR NOT NULL, 
	raw_text VARCHAR NOT NULL, 
	message_timestamp TIMESTAMP WITH TIME ZONE NOT NULL, 
	transaction_id INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	CONSTRAINT mpesa_messages_pkey PRIMARY KEY (id), 
	CONSTRAINT mpesa_messages_business_id_fkey FOREIGN KEY(business_id) REFERENCES businesses (id), 
	CONSTRAINT mpesa_messages_transaction_id_fkey FOREIGN KEY(transaction_id) REFERENCES transactions (id)
)

;


CREATE TABLE people (
	id SERIAL NOT NULL, 
	name VARCHAR NOT NULL, 
	phone VARCHAR, 
	type VARCHAR NOT NULL, 
	notes VARCHAR, 
	created_by INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT people_pkey PRIMARY KEY (id), 
	CONSTRAINT people_created_by_fkey FOREIGN KEY(created_by) REFERENCES users (id)
)

;


CREATE TABLE tracked_accounts (
	id SERIAL NOT NULL, 
	business_id INTEGER NOT NULL, 
	name VARCHAR NOT NULL, 
	account_type VARCHAR DEFAULT 'person'::character varying NOT NULL, 
	phone VARCHAR, 
	notes VARCHAR, 
	created_by INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	person_id INTEGER, 
	position_type VARCHAR DEFAULT 'tracked'::character varying NOT NULL, 
	CONSTRAINT tracked_accounts_pkey PRIMARY KEY (id), 
	CONSTRAINT fk_tracked_accounts_person_id FOREIGN KEY(person_id) REFERENCES people (id), 
	CONSTRAINT tracked_accounts_business_id_fkey FOREIGN KEY(business_id) REFERENCES businesses (id), 
	CONSTRAINT tracked_accounts_created_by_fkey FOREIGN KEY(created_by) REFERENCES users (id), 
	CONSTRAINT uq_person_position UNIQUE NULLS DISTINCT (person_id, position_type)
)

;


CREATE TABLE transactions (
	id SERIAL NOT NULL, 
	type VARCHAR NOT NULL, 
	amount NUMERIC(14, 2) NOT NULL, 
	description VARCHAR, 
	reference VARCHAR, 
	person_id INTEGER, 
	created_by INTEGER NOT NULL, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	business_id INTEGER NOT NULL, 
	amount_received NUMERIC(14, 2), 
	change_amount NUMERIC(14, 2), 
	payment_method VARCHAR, 
	CONSTRAINT transactions_pkey PRIMARY KEY (id), 
	CONSTRAINT transactions_business_id_fkey FOREIGN KEY(business_id) REFERENCES businesses (id), 
	CONSTRAINT transactions_created_by_fkey FOREIGN KEY(created_by) REFERENCES users (id), 
	CONSTRAINT transactions_person_id_fkey FOREIGN KEY(person_id) REFERENCES people (id)
)

;


CREATE TABLE users (
	id SERIAL NOT NULL, 
	email VARCHAR NOT NULL, 
	hashed_password VARCHAR NOT NULL, 
	full_name VARCHAR, 
	is_active INTEGER, 
	created_at TIMESTAMP WITH TIME ZONE DEFAULT now(), 
	updated_at TIMESTAMP WITH TIME ZONE, 
	CONSTRAINT users_pkey PRIMARY KEY (id)
)

;
