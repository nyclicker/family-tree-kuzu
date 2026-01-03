--
-- PostgreSQL database dump
--

\restrict jukLwUDiGI0wTOdQaP5hdixp7IBXVhzUrOKHpy3pg2nlkAfY116LLwKaXURlfAX

-- Dumped from database version 16.11 (Debian 16.11-1.pgdg13+1)
-- Dumped by pg_dump version 16.11 (Debian 16.11-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: reltype; Type: TYPE; Schema: public; Owner: app
--

CREATE TYPE public.reltype AS ENUM (
    'CHILD_OF',
    'EARLIEST_ANCESTOR'
);


ALTER TYPE public.reltype OWNER TO app;

--
-- Name: sex; Type: TYPE; Schema: public; Owner: app
--

CREATE TYPE public.sex AS ENUM (
    'M',
    'F',
    'U'
);


ALTER TYPE public.sex OWNER TO app;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: person; Type: TABLE; Schema: public; Owner: app
--

CREATE TABLE public.person (
    id character varying(36) NOT NULL,
    display_name character varying(200) NOT NULL,
    sex public.sex NOT NULL,
    birth_date date,
    death_date date,
    notes text
);


ALTER TABLE public.person OWNER TO app;

--
-- Name: relationship; Type: TABLE; Schema: public; Owner: app
--

CREATE TABLE public.relationship (
    id character varying(36) NOT NULL,
    from_person_id character varying(36) NOT NULL,
    to_person_id character varying(36),
    type public.reltype NOT NULL
);


ALTER TABLE public.relationship OWNER TO app;

--
-- Data for Name: person; Type: TABLE DATA; Schema: public; Owner: app
--

COPY public.person (id, display_name, sex, birth_date, death_date, notes) FROM stdin;
2e6e7e54-a7bb-44c2-9def-7845fcc74701	test	M	\N	\N	\N
e641f8a9-dfa0-4a39-be25-30207d19ea67	parent	M	\N	\N	\N
447669f4-67a9-494f-b50b-4d446090fc72	chld	F	\N	\N	\N
6d006638-4de7-40b1-9ae8-cede7beb9381	chld2	F	\N	\N	\N
e84b7583-740e-4f0d-b131-4a230f6469ac	p2	M	\N	\N	\N
bdcb031d-5de1-477a-9a36-50b60c6c4a1a	c2	M	\N	\N	\N
ba6929ef-81dd-43c3-b945-ad025bc8571a	c3	M	\N	\N	\N
b068d8f1-bb86-4adc-a5c0-c1c6b62b3863	c4	M	\N	\N	\N
d4b63425-0c18-4530-8b48-e91b544d8c8d	p3	M	\N	\N	\N
bec4b58b-5013-4e2c-b1dc-32ff97745fce	p4	M	\N	\N	\N
5607994b-951a-476c-b748-c6a491053e50	c31	M	\N	\N	\N
ec257a57-098a-45df-9153-10d0d88e2878	c32	M	\N	\N	\N
51a39861-c6b5-4adf-849d-2f743caf52d6	c41	M	\N	\N	\N
f1122ad7-28b5-4156-8308-af78474bd79e	c42	M	\N	\N	\N
ea0c9d34-2486-4ece-8593-47f11bf441aa	p5	M	\N	\N	\N
3d002f25-6e92-4cd3-94b7-2b2ffcba3da4	c51	F	\N	\N	\N
1cf467fb-e2d8-44a5-9906-baef315df841	ddd	M	\N	\N	\N
fdd943ce-0cb1-4360-b6b9-ec3b20f96fce	p6	U	\N	\N	\N
7ef321ef-b59a-44b8-86da-ccac5d13a50d	p7	F	\N	\N	\N
dc6e0b5d-226e-4ca6-ae27-22e80aaccc92	x	U	\N	\N	\N
0a2dab42-2f6c-4e3e-88f1-dcaa72264d67	new root	M	\N	\N	\N
1649ad4a-8591-4ecf-bb4b-2ee2dbf3d9af	new baby	F	\N	\N	\N
\.


--
-- Data for Name: relationship; Type: TABLE DATA; Schema: public; Owner: app
--

COPY public.relationship (id, from_person_id, to_person_id, type) FROM stdin;
c8e71b7d-3811-4fc1-8ca7-781bb385f745	e641f8a9-dfa0-4a39-be25-30207d19ea67	2e6e7e54-a7bb-44c2-9def-7845fcc74701	CHILD_OF
a6abc0b5-7e62-4893-a7b4-bc1b5591e419	447669f4-67a9-494f-b50b-4d446090fc72	e641f8a9-dfa0-4a39-be25-30207d19ea67	CHILD_OF
359470de-cdea-4461-8430-58194833567f	6d006638-4de7-40b1-9ae8-cede7beb9381	e641f8a9-dfa0-4a39-be25-30207d19ea67	CHILD_OF
4b04c56c-00d3-442a-b071-0bb8ce0e7d05	e84b7583-740e-4f0d-b131-4a230f6469ac	2e6e7e54-a7bb-44c2-9def-7845fcc74701	CHILD_OF
863dedc5-617b-4145-8bf9-3dfb8ebb26df	bdcb031d-5de1-477a-9a36-50b60c6c4a1a	e84b7583-740e-4f0d-b131-4a230f6469ac	CHILD_OF
1f94da2e-b954-4297-a6b8-1ecd3d383478	ba6929ef-81dd-43c3-b945-ad025bc8571a	e84b7583-740e-4f0d-b131-4a230f6469ac	CHILD_OF
5bc3df69-bffa-4914-9d68-4dc85beb90e2	b068d8f1-bb86-4adc-a5c0-c1c6b62b3863	e84b7583-740e-4f0d-b131-4a230f6469ac	CHILD_OF
27797098-352a-431c-8776-7626bd6bce6d	d4b63425-0c18-4530-8b48-e91b544d8c8d	e641f8a9-dfa0-4a39-be25-30207d19ea67	CHILD_OF
805364b4-6073-4f6e-8801-d0b8c8cca865	5607994b-951a-476c-b748-c6a491053e50	d4b63425-0c18-4530-8b48-e91b544d8c8d	CHILD_OF
e42e1be4-e599-432e-ac1d-3104c3d97d69	ec257a57-098a-45df-9153-10d0d88e2878	d4b63425-0c18-4530-8b48-e91b544d8c8d	CHILD_OF
a6f3f1ee-3cf6-4126-82c2-bcdd30b44b2c	bec4b58b-5013-4e2c-b1dc-32ff97745fce	2e6e7e54-a7bb-44c2-9def-7845fcc74701	CHILD_OF
fdac26d4-f728-4bf1-ad6c-51ca6eb0f273	51a39861-c6b5-4adf-849d-2f743caf52d6	bec4b58b-5013-4e2c-b1dc-32ff97745fce	CHILD_OF
e6bbea2a-0e0d-4c2f-9483-ef8716863a45	f1122ad7-28b5-4156-8308-af78474bd79e	bec4b58b-5013-4e2c-b1dc-32ff97745fce	CHILD_OF
1a8bdfd0-e1d9-4551-84d8-65686e5438dd	3d002f25-6e92-4cd3-94b7-2b2ffcba3da4	ea0c9d34-2486-4ece-8593-47f11bf441aa	CHILD_OF
148aed3e-8909-43a9-9994-c5c877b2bfc7	ea0c9d34-2486-4ece-8593-47f11bf441aa	2e6e7e54-a7bb-44c2-9def-7845fcc74701	CHILD_OF
fdefa1ca-54df-48a1-976b-ae2cc8dac6dc	dc6e0b5d-226e-4ca6-ae27-22e80aaccc92	e641f8a9-dfa0-4a39-be25-30207d19ea67	CHILD_OF
ff975887-0f0e-40d5-9f78-c233309859d1	7ef321ef-b59a-44b8-86da-ccac5d13a50d	fdd943ce-0cb1-4360-b6b9-ec3b20f96fce	CHILD_OF
530851ae-f705-490f-81cb-a7e79f60c3ec	fdd943ce-0cb1-4360-b6b9-ec3b20f96fce	e641f8a9-dfa0-4a39-be25-30207d19ea67	CHILD_OF
4a638027-f695-4573-95d3-7186d92da262	1cf467fb-e2d8-44a5-9906-baef315df841	447669f4-67a9-494f-b50b-4d446090fc72	CHILD_OF
15ae1447-df32-4249-ab5c-627dda0af1d1	1649ad4a-8591-4ecf-bb4b-2ee2dbf3d9af	0a2dab42-2f6c-4e3e-88f1-dcaa72264d67	CHILD_OF
\.


--
-- Name: person person_pkey; Type: CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.person
    ADD CONSTRAINT person_pkey PRIMARY KEY (id);


--
-- Name: relationship relationship_pkey; Type: CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.relationship
    ADD CONSTRAINT relationship_pkey PRIMARY KEY (id);


--
-- Name: relationship relationship_from_person_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.relationship
    ADD CONSTRAINT relationship_from_person_id_fkey FOREIGN KEY (from_person_id) REFERENCES public.person(id);


--
-- Name: relationship relationship_to_person_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: app
--

ALTER TABLE ONLY public.relationship
    ADD CONSTRAINT relationship_to_person_id_fkey FOREIGN KEY (to_person_id) REFERENCES public.person(id);


--
-- PostgreSQL database dump complete
--

\unrestrict jukLwUDiGI0wTOdQaP5hdixp7IBXVhzUrOKHpy3pg2nlkAfY116LLwKaXURlfAX

