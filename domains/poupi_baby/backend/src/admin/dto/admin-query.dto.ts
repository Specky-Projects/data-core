import { IsIn, IsOptional, IsString } from 'class-validator';

export class AdminListQueryDto {
  @IsOptional()
  @IsString()
  page?: string;

  @IsOptional()
  @IsString()
  limit?: string;

  @IsOptional()
  @IsString()
  q?: string;

  @IsOptional()
  @IsString()
  status?: string;

  @IsOptional()
  @IsString()
  marketplace?: string;

  @IsOptional()
  @IsString()
  role?: string;
}

export class UpdateUserRoleDto {
  @IsString()
  @IsIn(['free', 'premium', 'admin'])
  role: 'free' | 'premium' | 'admin';
}
