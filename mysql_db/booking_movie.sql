drop database if exists booking_movie;

create database booking_movie;

use booking_movie;

create table movie (
    id int not null auto_increment,
    name text,
    primary key (id)
);

insert into movie(name) values
    ('Phim 1'),
    ('Phim 2'),
    ('Phim 3');
